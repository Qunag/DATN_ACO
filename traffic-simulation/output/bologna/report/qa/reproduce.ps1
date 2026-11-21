Set-Location "D:\study\DATN\traffic-simulation"
$cfg = "scenarios/sumo-scenarios/bologna/acosta/run.sumocfg"
$common = @("-B", "-m", "scripts.osm.osm_runner",
    "--mode", "fleet", "--cfg", $cfg, "--seed", "51")
$dynamic = @("--incident-dynamic", "--incident-area",
    "300", "200", "1500", "1150", "--incident-count", "5")

foreach ($policy in @("original", "adaptive")) {
    python @common @dynamic --nogui --policy $policy `
        --demand-scale 1 `
        --output-dir output/bologna/regional-incident-reduced/verification
}

python @common @dynamic --policy adaptive --demand-scale 1 `
    --gui-delay 5 --pause-at 3400 `
    --output-dir output/bologna/regional-incident-reduced/gui