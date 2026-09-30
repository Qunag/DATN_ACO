/**
 * aco_engine.js – Giải thuật Đàn Kiến (Ant Colony Optimization) & Tìm đường đối chứng
 * Triển khai theo Báo cáo 1, 2, 3 của đề tài DATN: "Điều hướng Giao thông bằng Giải thuật Đàn Kiến"
 */

class ACORoutingEngine {
    constructor(graph, trafficModel, options = {}) {
        this.graph = graph;
        this.model = trafficModel;

        // Tham số thuật toán ACO (Báo cáo 1 & 3)
        this.nAnts = options.nAnts || 25;           // Số lượng kiến mỗi lần tìm đường
        this.iterations = options.iterations || 15; // Số vòng lặp
        this.alpha = options.alpha || 1.0;          // Trọng số pheromone (kinh nghiệm)
        this.beta = options.beta || 2.0;            // Trọng số heuristic (chất lượng giao thông)
        this.gamma = options.gamma || 1.5;          // Trọng số directional (hướng đích)
        this.rho = options.rho || 0.1;              // Tỷ lệ bay hơi pheromone
        this.Q = options.Q || 10.0;                 // Lượng pheromone để lại
        this.epsilon = 1e-6;                        // Tránh chia cho 0
    }

    /**
     * Tìm đường bằng thuật toán ACO (Ant Colony Optimization)
     */
    findRouteACO(sourceNode, targetNode) {
        if (sourceNode === targetNode) {
            return { path: [sourceNode], edges: [], travel_time: 0, distance: 0, cost: 0 };
        }

        let bestPath = null;
        let bestCost = Infinity;
        let bestTravelTime = Infinity;
        let bestDistance = Infinity;
        let bestEdges = [];

        const targetCoord = this.graph.nodes[targetNode];

        // ── Seed ban đầu bằng đường Dijkstra Traffic để đàn kiến có định hướng ──
        const seedResult = this.findRouteDijkstra(sourceNode, targetNode, "travel_time");
        if (seedResult && seedResult.path) {
            bestPath = seedResult.path;
            bestCost = seedResult.cost;
            bestTravelTime = seedResult.travel_time;
            bestDistance = seedResult.distance;
            bestEdges = seedResult.edges;

            // Tăng nhẹ pheromone cho tuyến đường mồi
            for (const eid of bestEdges) {
                if (this.model.edgeStates[eid]) {
                    this.model.edgeStates[eid].pheromone += 0.5;
                }
            }
        }

        // ── Vòng lặp các thế hệ kiến ──
        for (let iter = 0; iter < this.iterations; iter++) {
            const antPaths = [];

            for (let ant = 0; ant < this.nAnts; ant++) {
                const visited = new Set([sourceNode]);
                let curr = sourceNode;
                const path = [curr];
                const edges = [];
                let totalCost = 0;
                let totalTime = 0;
                let totalDist = 0;
                let reached = false;

                // Giới hạn số bước tối đa để tránh kiến lạc
                const maxSteps = Object.keys(this.graph.nodes).length;

                for (let step = 0; step < maxSteps; step++) {
                    if (curr === targetNode) {
                        reached = true;
                        break;
                    }

                    const neighbors = (this.graph.adjacency[curr] || []).filter(n => !visited.has(n));
                    if (neighbors.length === 0) {
                        break; // Gặp ngõ cụt
                    }

                    // Tính xác suất lựa chọn các nút láng giềng
                    const probs = [];
                    let sumProb = 0;

                    for (const nextNode of neighbors) {
                        const edgeId = `${curr}__TO__${nextNode}`;
                        const edgeState = this.model.edgeStates[edgeId];
                        const edgeData = this.graph.edges[edgeId];

                        if (!edgeState || !edgeData) continue;

                        // 1. Pheromone tau
                        const tau = Math.max(0.01, edgeState.pheromone);

                        // 2. Heuristic eta = 1 / (Cost + eps)
                        const eta = 1.0 / (edgeState.cost + this.epsilon);

                        // 3. Directional heuristic delta = 1 / (dist_to_target + eps)
                        const nCoord = this.graph.nodes[nextNode];
                        const distToTarget = haversineDistance(nCoord.lat, nCoord.lng, targetCoord.lat, targetCoord.lng);
                        const delta = 1.0 / (Math.max(50, distToTarget) + this.epsilon);

                        // P = tau^alpha * eta^beta * delta^gamma
                        const p =
                            Math.pow(tau, this.alpha) *
                            Math.pow(eta, this.beta) *
                            Math.pow(delta, this.gamma);

                        probs.push({ node: nextNode, edgeId: edgeId, p: p });
                        sumProb += p;
                    }

                    if (sumProb <= 0 || probs.length === 0) {
                        break;
                    }

                    // Roulette-wheel selection (Chọn theo xác suất bánh xe roulette)
                    const rand = Math.random() * sumProb;
                    let accum = 0;
                    let selected = probs[0];

                    for (const item of probs) {
                        accum += item.p;
                        if (rand <= accum) {
                            selected = item;
                            break;
                        }
                    }

                    // Di chuyển kiến sang nút được chọn
                    curr = selected.node;
                    visited.add(curr);
                    path.push(curr);
                    edges.push(selected.edgeId);

                    const eState = this.model.edgeStates[selected.edgeId];
                    const eData = this.graph.edges[selected.edgeId];
                    totalCost += eState.cost;
                    totalTime += eState.travel_time;
                    totalDist += eData.length;
                }

                if (reached) {
                    antPaths.push({
                        path: path,
                        edges: edges,
                        cost: totalCost,
                        travel_time: totalTime,
                        distance: totalDist
                    });

                    if (totalCost < bestCost) {
                        bestCost = totalCost;
                        bestPath = path;
                        bestEdges = edges;
                        bestTravelTime = totalTime;
                        bestDistance = totalDist;
                    }
                }
            }

            // ── Cập nhật Pheromone sau mỗi thế hệ (Offline update) ──
            if (bestEdges.length > 0) {
                const deltaPheromone = this.Q / Math.max(0.1, bestCost);
                for (const eid of bestEdges) {
                    if (this.model.edgeStates[eid]) {
                        this.model.edgeStates[eid].pheromone += deltaPheromone;
                    }
                }
            }
        }

        return {
            algorithm: "ACO (Ant Colony)",
            path: bestPath,
            edges: bestEdges,
            cost: Math.round(bestCost * 100) / 100,
            travel_time: Math.round(bestTravelTime),
            distance: Math.round(bestDistance)
        };
    }

    /**
     * Thuật toán Dijkstra (Hỗ trợ 2 chế độ: 'travel_time' hoặc 'distance')
     */
    findRouteDijkstra(sourceNode, targetNode, mode = "travel_time") {
        if (sourceNode === targetNode) {
            return { path: [sourceNode], edges: [], travel_time: 0, distance: 0, cost: 0 };
        }

        const distances = {};
        const previous = {};
        const edgeUsed = {};
        const unvisited = new Set(Object.keys(this.graph.nodes));

        for (const node of Object.keys(this.graph.nodes)) {
            distances[node] = Infinity;
        }
        distances[sourceNode] = 0;

        while (unvisited.size > 0) {
            // Tìm nút có khoảng cách nhỏ nhất trong unvisited
            let minNode = null;
            let minDist = Infinity;
            for (const node of unvisited) {
                if (distances[node] < minDist) {
                    minDist = distances[node];
                    minNode = node;
                }
            }

            if (!minNode || minDist === Infinity || minNode === targetNode) {
                break;
            }

            unvisited.delete(minNode);

            for (const neighbor of (this.graph.adjacency[minNode] || [])) {
                if (!unvisited.has(neighbor)) continue;

                const edgeId = `${minNode}__TO__${neighbor}`;
                const edgeData = this.graph.edges[edgeId];
                const edgeState = this.model.edgeStates[edgeId];

                if (!edgeData || !edgeState) continue;

                // Trọng số cạnh tùy theo chế độ
                const weight = (mode === "travel_time") ? edgeState.travel_time : edgeData.length;
                const alt = distances[minNode] + weight;

                if (alt < distances[neighbor]) {
                    distances[neighbor] = alt;
                    previous[neighbor] = minNode;
                    edgeUsed[neighbor] = edgeId;
                }
            }
        }

        // Tái tạo đường đi
        if (distances[targetNode] === Infinity) {
            return null; // Không có đường đi
        }

        const path = [];
        const edges = [];
        let curr = targetNode;

        while (curr) {
            path.unshift(curr);
            if (previous[curr]) {
                edges.unshift(edgeUsed[curr]);
            }
            curr = previous[curr];
        }

        // Tính tổng thời gian, khoảng cách và chi phí thực tế
        let totalTime = 0;
        let totalDist = 0;
        let totalCost = 0;

        for (const eid of edges) {
            const eState = this.model.edgeStates[eid];
            const eData = this.graph.edges[eid];
            if (eState && eData) {
                totalTime += eState.travel_time;
                totalDist += eData.length;
                totalCost += eState.cost;
            }
        }

        return {
            algorithm: mode === "travel_time" ? "Dijkstra (Traffic-Aware)" : "Dijkstra (Static Shortest Distance)",
            path: path,
            edges: edges,
            cost: Math.round(totalCost * 100) / 100,
            travel_time: Math.round(totalTime),
            distance: Math.round(totalDist)
        };
    }

    /**
     * So sánh đồng thời 3 giải thuật cho một cặp điểm (O, D)
     */
    compareAllAlgorithms(sourceNode, targetNode) {
        const aco = this.findRouteACO(sourceNode, targetNode);
        const dijkstraDynamic = this.findRouteDijkstra(sourceNode, targetNode, "travel_time");
        const dijkstraStatic = this.findRouteDijkstra(sourceNode, targetNode, "distance");

        return {
            source: this.graph.nodes[sourceNode] ? this.graph.nodes[sourceNode].name : sourceNode,
            target: this.graph.nodes[targetNode] ? this.graph.nodes[targetNode].name : targetNode,
            aco: aco,
            dijkstra_dynamic: dijkstraDynamic,
            dijkstra_static: dijkstraStatic,
            time_savings_aco_vs_static: dijkstraStatic && aco ?
                Math.max(0, dijkstraStatic.travel_time - aco.travel_time) : 0,
            time_savings_pct: dijkstraStatic && aco && dijkstraStatic.travel_time > 0 ?
                Math.round(((dijkstraStatic.travel_time - aco.travel_time) / dijkstraStatic.travel_time) * 100) : 0
        };
    }
}

// Xuất biến toàn cục
if (typeof window !== "undefined") {
    window.ACORoutingEngine = ACORoutingEngine;
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { ACORoutingEngine };
}
