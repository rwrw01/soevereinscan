from app.models import Scan, DiscoveredResource, IpAnalysis, TracerouteResult

def test_scan_model_exists():
    assert Scan.__tablename__ == "scans"

def test_discovered_resource_model_exists():
    assert DiscoveredResource.__tablename__ == "discovered_resources"

def test_ip_analysis_model_exists():
    assert IpAnalysis.__tablename__ == "ip_analysis"

def test_traceroute_result_model_exists():
    assert TracerouteResult.__tablename__ == "traceroute_results"
