"""
Feature Flags for CSOKi Data Source Migration.

Provides centralized control over data source selection for gradual rollout
and easy rollback during the migration from external APIs to local data.
"""

import os
import random
from typing import Optional
from app.core.config import settings


class FeatureFlags:
    """
    Centralized feature flag management for data source migration.
    
    Supports:
    - Boolean feature flags via environment variables
    - Percentage-based gradual rollout
    - Request-level overrides for testing
    - Fallback behavior configuration
    """
    
    # Environment variable names
    _ENABLE_LOCAL_PROPERTIES = "ENABLE_LOCAL_PROPERTIES"
    _ENABLE_LOCAL_DEMOGRAPHICS = "ENABLE_LOCAL_DEMOGRAPHICS"
    _ENABLE_GRADUAL_ROLLOUT = "ENABLE_GRADUAL_ROLLOUT"
    _ROLLOUT_PERCENTAGE = "ROLLOUT_PERCENTAGE"
    _FALLBACK_TO_EXTERNAL = "FALLBACK_TO_EXTERNAL"
    _DATA_SOURCE_MODE = "DATA_SOURCE_MODE"
    
    # Default values
    _DEFAULTS = {
        _ENABLE_LOCAL_PROPERTIES: False,
        _ENABLE_LOCAL_DEMOGRAPHICS: False,
        _ENABLE_GRADUAL_ROLLOUT: True,
        _ROLLOUT_PERCENTAGE: 0,
        _FALLBACK_TO_EXTERNAL: True,
        _DATA_SOURCE_MODE: "external",  # external, local, hybrid
    }
    
    @classmethod
    def _get_bool_flag(cls, env_var: str) -> bool:
        """Get boolean value from environment variable."""
        value = os.getenv(env_var, str(cls._DEFAULTS[env_var]))
        return value.lower() in ("true", "1", "yes", "on")
    
    @classmethod
    def _get_int_flag(cls, env_var: str) -> int:
        """Get integer value from environment variable."""
        try:
            return int(os.getenv(env_var, str(cls._DEFAULTS[env_var])))
        except (ValueError, TypeError):
            return cls._DEFAULTS[env_var]
    
    @classmethod
    def _get_str_flag(cls, env_var: str) -> str:
        """Get string value from environment variable."""
        return os.getenv(env_var, str(cls._DEFAULTS[env_var]))
    
    @classmethod
    def _should_use_local_for_request(cls) -> bool:
        """
        Determine if this request should use local data based on rollout percentage.
        Uses random sampling for gradual rollout.
        """
        if not cls._get_bool_flag(cls._ENABLE_GRADUAL_ROLLOUT):
            return True
        
        rollout_pct = cls._get_int_flag(cls._ROLLOUT_PERCENTAGE)
        if rollout_pct <= 0:
            return False
        if rollout_pct >= 100:
            return True
        
        # Random sampling for gradual rollout
        return random.randint(1, 100) <= rollout_pct
    
    # --- Property Data Source Flags ---
    
    @classmethod
    def use_local_property_data(cls, request_override: Optional[bool] = None) -> bool:
        """
        Should we use local property database instead of ATTOM API?
        
        Args:
            request_override: Force a specific choice for testing (bypasses rollout logic)
            
        Returns:
            True if should use local property database, False if should use ATTOM API
        """
        if request_override is not None:
            return request_override
        
        # Check if local properties are globally enabled
        if not cls._get_bool_flag(cls._ENABLE_LOCAL_PROPERTIES):
            return False
        
        # Check data source mode
        mode = cls._get_str_flag(cls._DATA_SOURCE_MODE)
        if mode == "external":
            return False
        elif mode == "local":
            return True
        elif mode == "hybrid":
            return cls._should_use_local_for_request()
        
        # Default fallback
        return False
    
    @classmethod
    def has_local_property_db(cls) -> bool:
        """Check if local property database is configured."""
        return hasattr(settings, 'LOCAL_PROPERTY_DB_URL') and settings.LOCAL_PROPERTY_DB_URL is not None
    
    @classmethod
    def should_fallback_to_attom(cls) -> bool:
        """Should we fallback to ATTOM API if local property data fails?"""
        return cls._get_bool_flag(cls._FALLBACK_TO_EXTERNAL) and hasattr(settings, 'ATTOM_API_KEY') and settings.ATTOM_API_KEY
    
    # --- Demographics Data Source Flags ---
    
    @classmethod
    def use_local_demographics(cls, request_override: Optional[bool] = None) -> bool:
        """
        Should we use local census database instead of ArcGIS API?
        
        Args:
            request_override: Force a specific choice for testing (bypasses rollout logic)
            
        Returns:
            True if should use local census database, False if should use ArcGIS API
        """
        if request_override is not None:
            return request_override
        
        # Check if local demographics are globally enabled
        if not cls._get_bool_flag(cls._ENABLE_LOCAL_DEMOGRAPHICS):
            return False
        
        # Check data source mode
        mode = cls._get_str_flag(cls._DATA_SOURCE_MODE)
        if mode == "external":
            return False
        elif mode == "local":
            return True
        elif mode == "hybrid":
            return cls._should_use_local_for_request()
        
        # Default fallback
        return False
    
    @classmethod
    def has_local_census_db(cls) -> bool:
        """Check if local census database is configured."""
        return hasattr(settings, 'LOCAL_CENSUS_DB_URL') and settings.LOCAL_CENSUS_DB_URL is not None
    
    @classmethod
    def should_fallback_to_arcgis(cls) -> bool:
        """Should we fallback to ArcGIS API if local demographics data fails?"""
        return cls._get_bool_flag(cls._FALLBACK_TO_EXTERNAL) and hasattr(settings, 'ARCGIS_API_KEY') and settings.ARCGIS_API_KEY
    
    # --- Global Data Source Control ---
    
    @classmethod
    def get_data_source_mode(cls) -> str:
        """Get current data source mode: external, local, or hybrid."""
        return cls._get_str_flag(cls._DATA_SOURCE_MODE)
    
    @classmethod
    def get_rollout_percentage(cls) -> int:
        """Get current rollout percentage (0-100)."""
        return cls._get_int_flag(cls._ROLLOUT_PERCENTAGE)
    
    @classmethod
    def is_gradual_rollout_enabled(cls) -> bool:
        """Is gradual percentage-based rollout enabled?"""
        return cls._get_bool_flag(cls._ENABLE_GRADUAL_ROLLOUT)
    
    # --- Emergency Controls ---
    
    @classmethod
    def disable_local_data(cls):
        """
        Emergency disable of all local data sources.
        
        This is intended for automated health checks that detect issues
        with local data and need to immediately fall back to external APIs.
        
        Note: This modifies environment variables for the current process only.
        For persistent changes, update the actual environment configuration.
        """
        os.environ[cls._ENABLE_LOCAL_PROPERTIES] = "false"
        os.environ[cls._ENABLE_LOCAL_DEMOGRAPHICS] = "false"
        os.environ[cls._ROLLOUT_PERCENTAGE] = "0"
        os.environ[cls._DATA_SOURCE_MODE] = "external"
    
    @classmethod
    def enable_local_data(cls, percentage: int = 100):
        """
        Enable local data sources with specified rollout percentage.
        
        Args:
            percentage: Rollout percentage (0-100)
        """
        if not (0 <= percentage <= 100):
            raise ValueError("Percentage must be between 0 and 100")
        
        os.environ[cls._ENABLE_LOCAL_PROPERTIES] = "true"
        os.environ[cls._ENABLE_LOCAL_DEMOGRAPHICS] = "true"
        os.environ[cls._ROLLOUT_PERCENTAGE] = str(percentage)
        
        if percentage == 100:
            os.environ[cls._DATA_SOURCE_MODE] = "local"
        else:
            os.environ[cls._DATA_SOURCE_MODE] = "hybrid"
    
    # --- Status and Health Checks ---
    
    @classmethod
    def get_status(cls) -> dict:
        """
        Get current feature flag status for monitoring and debugging.
        
        Returns:
            Dictionary with current flag states and configuration
        """
        return {
            "data_source_mode": cls.get_data_source_mode(),
            "rollout_percentage": cls.get_rollout_percentage(),
            "gradual_rollout_enabled": cls.is_gradual_rollout_enabled(),
            "flags": {
                "local_properties_enabled": cls._get_bool_flag(cls._ENABLE_LOCAL_PROPERTIES),
                "local_demographics_enabled": cls._get_bool_flag(cls._ENABLE_LOCAL_DEMOGRAPHICS),
                "fallback_to_external": cls._get_bool_flag(cls._FALLBACK_TO_EXTERNAL),
            },
            "database_availability": {
                "local_property_db": cls.has_local_property_db(),
                "local_census_db": cls.has_local_census_db(),
                "attom_api_key": hasattr(settings, 'ATTOM_API_KEY') and settings.ATTOM_API_KEY is not None,
                "arcgis_api_key": hasattr(settings, 'ARCGIS_API_KEY') and settings.ARCGIS_API_KEY is not None,
            }
        }
    
    @classmethod
    def validate_configuration(cls) -> list[str]:
        """
        Validate feature flag configuration and return any warnings/errors.
        
        Returns:
            List of warning/error messages, empty if configuration is valid
        """
        warnings = []
        
        # Check for local data enabled without local databases
        if cls.use_local_property_data() and not cls.has_local_property_db():
            warnings.append("Local property data enabled but LOCAL_PROPERTY_DB_URL not configured")
        
        if cls.use_local_demographics() and not cls.has_local_census_db():
            warnings.append("Local demographics enabled but LOCAL_CENSUS_DB_URL not configured")
        
        # Check for missing fallback APIs
        if not cls.should_fallback_to_attom() and cls.use_local_property_data():
            warnings.append("No fallback to ATTOM API configured - could cause failures if local DB is down")
        
        if not cls.should_fallback_to_arcgis() and cls.use_local_demographics():
            warnings.append("No fallback to ArcGIS API configured - could cause failures if local DB is down")
        
        # Check rollout percentage bounds
        rollout_pct = cls.get_rollout_percentage()
        if not (0 <= rollout_pct <= 100):
            warnings.append(f"Invalid rollout percentage: {rollout_pct} (must be 0-100)")
        
        return warnings


# Convenience functions for common use cases

def use_local_properties() -> bool:
    """Convenience function: Should use local property database?"""
    return FeatureFlags.use_local_property_data()

def use_local_demographics() -> bool:
    """Convenience function: Should use local demographics database?"""
    return FeatureFlags.use_local_demographics()

def data_source_is_local() -> bool:
    """Convenience function: Are we using local data sources?"""
    return FeatureFlags.use_local_property_data() or FeatureFlags.use_local_demographics()

def data_source_is_hybrid() -> bool:
    """Convenience function: Are we in hybrid mode?"""
    return FeatureFlags.get_data_source_mode() == "hybrid"


# Example usage in route handlers:
"""
from app.core.feature_flags import FeatureFlags

async def search_properties(request):
    if FeatureFlags.use_local_property_data():
        try:
            return await local_property_service.search(request)
        except Exception as e:
            if FeatureFlags.should_fallback_to_attom():
                logger.warning(f"Local property search failed, falling back to ATTOM: {e}")
                return await attom_service.search(request)
            else:
                raise
    else:
        return await attom_service.search(request)
"""