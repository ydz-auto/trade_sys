# Engines Migration Boundary

`engines/` is the destination for stateless compute and external IO adapters.

Allowed here:

- pure compute
- vectorized/GPU calculations
- exchange, websocket, Kafka, storage, and database adapters
- deterministic helper code with no owned runtime state

Forbidden here:

- replay cursor
- pending orders
- positions
- feature availability
- signal sequence/cooldown
- mutable runtime lifecycle

Migration rule:

1. If a module owns mutable trading state, move the state into the owning runtime first.
2. Extract only the stateless calculation or IO adapter into `engines/`.
3. Runtime calls the engine; engine never calls runtime.
4. Add ownership checks for any state touched by the runtime.

Current compatibility:

- Existing `services/` modules remain in place until each module is split.
- New code should use `engines/` for stateless compute and adapters.
