"""
Safe wrapper for listings routes - makes Crexi automation optional.
Use this if Playwright won't install in production.
"""

# At the top of listings.py, wrap the Crexi imports:

try:
    from app.services.crexi_automation import fetch_crexi_area, CrexiAutomationError
    CREXI_AVAILABLE = True
except ImportError as e:
    CREXI_AVAILABLE = False
    import logging
    logging.warning(f"Crexi automation disabled: {e}")
    
    # Stub implementation
    class CrexiAutomationError(Exception):
        pass
    
    async def fetch_crexi_area(*args, **kwargs):
        raise CrexiAutomationError("Crexi automation not available in this environment")


# Then in the endpoint:
@router.post("/fetch-crexi-area", response_model=CrexiAreaResponse)
async def fetch_crexi_area_endpoint(
    request: CrexiAreaRequest,
    db: Session = Depends(get_db)
):
    if not CREXI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Crexi automation is not available in this environment. Please contact support."
        )
    
    # ... rest of your existing code
