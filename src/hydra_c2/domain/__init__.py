"""Domain Layer — Core business logic, entities, and interfaces.

This layer has ZERO external dependencies. It defines:
- Entities: Actor, Event, Transmission, Location, Equipment, Unit
- Value Objects: GeoPosition, Confidence, Affiliation
- Interfaces: Repository contracts, Messaging contracts

Dependency Rule: Nothing in this layer imports from application or infrastructure.
"""
