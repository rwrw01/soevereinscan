def test_ripestat_service_has_get_country():
    from app.services.ripestat import RipeStatService
    service = RipeStatService()
    assert hasattr(service, "get_country")
