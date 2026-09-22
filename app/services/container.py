"""Service container and dependency injection framework.

This module provides:
- A base Service class for all domain services
- A ServiceContainer for managing service lifecycle and dependencies
- Decorators for registering services
- Utilities for retrieving services in API endpoints
"""

from typing import Any, Dict, Optional, Type, TypeVar, Callable
from abc import ABC, abstractmethod

T = TypeVar('T', bound='Service')


class Service(ABC):
    """Base class for all domain services.
    
    Services encapsulate business logic and coordinate between:
    - Data models
    - External APIs/integrations
    - Other services
    
    Services are instantiated once and reused across requests.
    """
    
    def __init__(self, container: 'ServiceContainer'):
        """Initialize service with access to container for service dependencies.
        
        Args:
            container: ServiceContainer instance for accessing other services
        """
        self.container = container
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize service resources (connections, caches, etc.)."""
        pass
    
    def shutdown(self) -> None:
        """Cleanup service resources. Override as needed."""
        pass


class ServiceContainer:
    """Dependency injection container for managing services.
    
    Features:
    - Register service classes with factory methods
    - Lazy instantiation of services
    - Shared service instances (singleton pattern)
    - Service lifecycle management (init, shutdown)
    
    Example:
        container = ServiceContainer()
        container.register(StudentService)
        student_service = container.get(StudentService)
    """
    
    def __init__(self):
        """Initialize empty service container."""
        self._services: Dict[str, Service] = {}
        self._factories: Dict[str, Callable[['ServiceContainer'], Service]] = {}
        self._service_classes: Dict[str, Type[Service]] = {}
    
    def register(self, service_class: Type[T], factory: Optional[Callable[['ServiceContainer'], T]] = None) -> None:
        """Register a service class in the container.
        
        If no factory is provided, the service class will be instantiated directly.
        
        Args:
            service_class: Service class to register
            factory: Optional custom factory function for creating the service
        """
        key = service_class.__name__
        self._service_classes[key] = service_class
        
        if factory:
            self._factories[key] = factory
        else:
            # Default factory: instantiate the class
            self._factories[key] = lambda container: service_class(container)
    
    def get(self, service_class: Type[T]) -> T:
        """Get a service instance, creating it if needed.
        
        Args:
            service_class: Service class to retrieve
            
        Returns:
            Service instance (singleton)
            
        Raises:
            KeyError: If service is not registered
        """
        key = service_class.__name__
        
        # Return cached instance if available
        if key in self._services:
            return self._services[key]
        
        # Create new instance
        if key not in self._factories:
            raise KeyError(f"Service {key} not registered in container")
        
        factory = self._factories[key]
        service = factory(self)
        service.initialize()
        
        # Cache for future use
        self._services[key] = service
        
        return service
    
    def has(self, service_class: Type[Service]) -> bool:
        """Check if a service is registered.
        
        Args:
            service_class: Service class to check
            
        Returns:
            True if service is registered, False otherwise
        """
        key = service_class.__name__
        return key in self._factories
    
    def shutdown_all(self) -> None:
        """Shutdown all active services."""
        for service in self._services.values():
            try:
                service.shutdown()
            except Exception as e:
                print(f"Error shutting down {type(service).__name__}: {e}")
        self._services.clear()


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get or create the global service container."""
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def set_container(container: ServiceContainer) -> None:
    """Set the global service container (useful for testing)."""
    global _container
    _container = container


def get_service(service_class: Type[T]) -> T:
    """Get a service from the global container.
    
    Convenience function for use in API endpoints and other code.
    
    Args:
        service_class: Service class to retrieve
        
    Returns:
        Service instance
        
    Example:
        from app.services.container import get_service
        from app.services.boirsu import BoiRsuService
        
        @bp.route('/courses')
        def list_courses():
            service = get_service(BoiRsuService)
            courses = service.list_courses()
            return jsonify(courses)
    """
    return get_container().get(service_class)
