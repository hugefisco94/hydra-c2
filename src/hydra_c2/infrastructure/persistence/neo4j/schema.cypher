// =============================================================================
// HYDRA-C2 Neo4j Graph Schema
// Layer 4: Persistence Layer — Relationship Graph Store
// =============================================================================

// --- Constraints (uniqueness + existence) ---
CREATE CONSTRAINT actor_id IF NOT EXISTS FOR (a:Actor) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE;
CREATE CONSTRAINT equipment_id IF NOT EXISTS FOR (eq:Equipment) REQUIRE eq.id IS UNIQUE;
CREATE CONSTRAINT unit_id IF NOT EXISTS FOR (u:Unit) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT transmission_id IF NOT EXISTS FOR (t:Transmission) REQUIRE t.id IS UNIQUE;

// --- Indexes for common queries ---
CREATE INDEX actor_callsign IF NOT EXISTS FOR (a:Actor) ON (a.callsign);
CREATE INDEX actor_affiliation IF NOT EXISTS FOR (a:Actor) ON (a.affiliation);
CREATE INDEX actor_type IF NOT EXISTS FOR (a:Actor) ON (a.type);
CREATE INDEX event_type IF NOT EXISTS FOR (e:Event) ON (e.type);
CREATE INDEX event_timestamp IF NOT EXISTS FOR (e:Event) ON (e.timestamp);
CREATE INDEX location_name IF NOT EXISTS FOR (l:Location) ON (l.name);
CREATE INDEX transmission_freq IF NOT EXISTS FOR (t:Transmission) ON (t.freq_mhz);
CREATE INDEX unit_name IF NOT EXISTS FOR (u:Unit) ON (u.name);

// --- Spatial Index (Neo4j Spatial) ---
CREATE POINT INDEX actor_location IF NOT EXISTS FOR (a:Actor) ON (a.location);
CREATE POINT INDEX event_location IF NOT EXISTS FOR (e:Event) ON (e.location);
CREATE POINT INDEX location_coords IF NOT EXISTS FOR (l:Location) ON (l.coords);

// =============================================================================
// Sample Data Loading Templates (Cypher MERGE patterns)
// =============================================================================

// --- Create Actor with spatial data ---
// MERGE (a:Actor {id: $id})
// SET a.callsign = $callsign,
//     a.type = $type,
//     a.affiliation = $affiliation,
//     a.location = point({latitude: $lat, longitude: $lon}),
//     a.last_seen = datetime($timestamp),
//     a.source = $source

// --- Create Event and link to Actor ---
// MERGE (e:Event {id: $event_id})
// SET e.type = $event_type,
//     e.timestamp = datetime($timestamp),
//     e.description = $description,
//     e.location = point({latitude: $lat, longitude: $lon}),
//     e.confidence = $confidence

// WITH e
// MATCH (a:Actor {id: $actor_id})
// MERGE (a)-[:PARTICIPATED_IN {role: $role}]->(e)

// --- Link Actor to Location observation ---
// MATCH (a:Actor {id: $actor_id})
// MERGE (l:Location {id: $location_id})
// SET l.name = $name, l.coords = point({latitude: $lat, longitude: $lon})
// MERGE (a)-[:OBSERVED_AT {timestamp: datetime($ts), source: $source}]->(l)

// --- Transmission detection from SDR ---
// MERGE (t:Transmission {id: $id})
// SET t.freq_mhz = $freq, t.power_dbm = $power,
//     t.modulation = $modulation, t.bearing_deg = $bearing,
//     t.timestamp = datetime($ts), t.source_sdr = $sdr
// WITH t
// MATCH (a:Actor {id: $actor_id})
// MERGE (a)-[:TRANSMITTED]->(t)

// =============================================================================
// Analytical Queries (Cypher library)
// =============================================================================

// Q1: Co-located actors within 2 hours
// MATCH (a1:Actor)-[:OBSERVED_AT]->(l:Location)<-[:OBSERVED_AT]-(a2:Actor)
// WHERE a1 <> a2
//   AND abs(duration.between(a1.last_seen, a2.last_seen).seconds) < 7200
// RETURN a1.callsign, a2.callsign, l.name,
//        point.distance(a1.location, a2.location) AS distance_m

// Q2: Network of a specific actor (3 hops)
// MATCH path = (a:Actor {callsign: $callsign})-[*1..3]-(connected)
// RETURN path

// Q3: Transmission source network analysis
// MATCH (t:Transmission {freq_mhz: $freq})<-[:TRANSMITTED]-(a:Actor)
//       -[:MEMBER_OF*1..3]->(u:Unit)
// RETURN a.callsign, u.name, t.bearing_deg, t.timestamp

// Q4: PageRank for actor importance
// CALL gds.pageRank.stream('actor-graph', {relationshipTypes: ['CO_LOCATED_WITH', 'MEMBER_OF']})
// YIELD nodeId, score
// RETURN gds.util.asNode(nodeId).callsign AS actor, score
// ORDER BY score DESC LIMIT 20

// Q5: Community detection
// CALL gds.louvain.stream('actor-graph')
// YIELD nodeId, communityId
// RETURN gds.util.asNode(nodeId).callsign AS actor, communityId
// ORDER BY communityId
