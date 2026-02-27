# AI-Friendly Codebase: Structure & Documentation Best Practices

> These guidelines ensure that AI agents (Claude Code, Cursor, Copilot, orchestrators like Debussy) can quickly index, understand, and safely modify any codebase — regardless of size.

---

## 1. Repository-Level Meta Files

### CLAUDE.md (Root)
Every repository MUST have a `CLAUDE.md` in the root directory. This is the single most impactful file for AI agent comprehension. It should contain:

- **Project purpose** — one paragraph explaining what this system does and for whom
- **Architecture overview** — high-level description of modules/services and how they communicate
- **Tech stack** — languages, frameworks, key libraries with versions that matter
- **Build & run instructions** — exact commands to build, test, run locally
- **Naming conventions** — patterns used for classes, methods, variables, files, packages
- **Key architectural decisions** — brief summary with links to ADRs
- **Module map** — which directory owns which domain concept
- **Known constraints** — things an agent must NOT change (e.g., "do not modify the auth module without explicit approval")
- **Testing strategy** — how to run tests, what coverage is expected, test naming conventions

### CLAUDE.md (Per-Module)
Place additional `CLAUDE.md` files in subdirectories to provide module-specific context:
- Module responsibility and bounded context
- Internal patterns specific to this module
- Dependencies on other modules
- Edge cases and invariants unique to this module

### Other Meta Files
- `CONTRIBUTING.md` — contribution workflow, PR conventions, branch strategy
- `.cursor/rules` — if using Cursor, keep in sync with CLAUDE.md
- `docs/GLOSSARY.md` — domain-specific terms and their definitions (critical for DDD projects)

---

## 2. Architecture Documentation

### Architecture Decision Records (ADRs)
Maintain a `docs/adr/` folder with files like `001-event-sourcing-for-orders.md`. Each ADR should follow this structure:

```
# ADR-NNN: Title

## Status: Accepted | Superseded | Deprecated

## Context
What problem we faced.

## Decision
What we chose and why.

## Consequences
What trade-offs this introduces.
```

ADRs are critical because they tell AI agents **why** the code is structured a certain way, preventing agents from "improving" things back to a state that was already considered and rejected.

### ARCHITECTURE.md
Include a `docs/ARCHITECTURE.md` with:
- System context diagram (Mermaid preferred — AI agents parse it natively)
- Component/module diagram
- Data flow for key use cases
- Integration points (APIs, message queues, databases)

Use Mermaid for all diagrams:
```mermaid
graph TD
    A[API Gateway] --> B[Invoice Service]
    A --> C[Payment Service]
    B --> D[(PostgreSQL)]
    C --> E[(Redis)]
    B -->|domain events| F[Kafka]
    C -->|domain events| F
```

---

## 3. Directory Structure

### Screaming Architecture
Structure directories by **domain concept**, not by technical layer:

```
✅ GOOD — domain-driven structure
src/
  invoices/
    Invoice.java
    InvoiceService.java
    InvoiceRepository.java
    InvoiceController.java
    InvoiceMapper.java
  payments/
    Payment.java
    PaymentService.java
    ...
  shared/
    money/
    events/
```

```
❌ BAD — layer-driven structure
src/
  controllers/
    InvoiceController.java
    PaymentController.java
  services/
    InvoiceService.java
    PaymentService.java
  repositories/
    ...
```

Domain-driven structure allows an AI agent to load a single folder and have full context for one feature, instead of jumping across the entire tree.

### Package/Module Descriptions
- **Java**: Use `package-info.java` in every package with a Javadoc comment explaining the package's responsibility
- **Python**: Use `__init__.py` with a module docstring
- **TypeScript**: Use `index.ts` barrel exports with a JSDoc comment at the top

### File Size Discipline
- **Hard limit**: No file should exceed 500 lines. Aim for 200-300.
- **Rationale**: AI agents lose context accuracy in long files. Smaller, focused files = better agent performance.
- If a file grows beyond the limit, it's a signal to extract a new module/class.

---

## 4. Code Documentation Strategy

### The "Why, Not What" Principle
AI agents can read code and understand *what* it does. They need humans to explain *why*:

```java
// ❌ BAD — states what the code does (agent already sees this)
// Sets the discount to 10%
invoice.setDiscount(0.10);

// ✅ GOOD — explains why and captures business context
// Returning customers with 12+ months history get a loyalty discount.
// This is a business rule from the 2024 pricing overhaul (see ADR-012).
invoice.setDiscount(0.10);
```

### Document Invariants and Edge Cases
```java
/**
 * Must be called after any line item modification.
 * Totals are denormalized for query performance (not event-sourced).
 * 
 * Invariant: total must never be negative. If discount exceeds
 * subtotal, total is clamped to zero (see ADR-003).
 */
public void recalculateTotals() { ... }
```

### Interface and Public API Documentation
Every public interface/class should have:
- One sentence: what is this?
- Behavioral contract: what guarantees does it provide?
- Thread safety notes (if applicable)
- Example usage (for non-obvious APIs)

---

## 5. Type Safety and Contracts

### Strong Typing Over Primitives
- **TypeScript** over JavaScript — always
- **Python type hints** — use them everywhere, run mypy in CI
- **Java records/sealed classes** — for DTOs and domain objects
- **Avoid primitive obsession** — `Money` instead of `BigDecimal`, `EmailAddress` instead of `String`

Strong types give AI agents enormous context without reading implementation:
```typescript
// Agent immediately understands the domain from types alone
function processPayment(
  invoice: Invoice,
  method: PaymentMethod,
  amount: Money
): Result<PaymentConfirmation, PaymentError>
```

### API Contracts
- **REST APIs**: Maintain OpenAPI/Swagger specs (`docs/openapi.yaml`)
- **Async APIs**: Use AsyncAPI specs for event-driven systems
- **GraphQL**: Keep the schema as the source of truth
- These specs serve as a map of system boundaries for AI agents.

---

## 6. Testing as Documentation

### Descriptive Test Names
Tests should read as behavioral specifications:

```java
// ✅ Agent learns business rules from test names alone
@Test void shouldRejectInvoiceWhenTotalExceedsClientCreditLimit() { }
@Test void shouldApplyLoyaltyDiscountForCustomersWithOver12MonthsHistory() { }
@Test void shouldSendNotificationWhenPaymentIsOverdue() { }

// ❌ Agent learns nothing
@Test void testInvoice() { }
@Test void testDiscount() { }
```

### Test Structure
- Use Arrange-Act-Assert (AAA) or Given-When-Then pattern consistently
- Group tests by feature/behavior, not by class
- Integration tests should document system boundaries and external dependencies

---

## 7. Dependency and Configuration Management

### Explicit Dependencies
- Lock file always committed (`package-lock.json`, `poetry.lock`, `gradle.lockfile`)
- `.env.example` with all required environment variables documented
- `docker-compose.yml` for local infrastructure dependencies

### Configuration Documentation
```yaml
# .env.example
# Database connection (PostgreSQL 15+)
DATABASE_URL=postgresql://user:pass@localhost:5432/myapp

# Payment gateway API key (get from: https://dashboard.stripe.com/apikeys)
STRIPE_API_KEY=sk_test_...

# Feature flags
FEATURE_NEW_PRICING=false  # Enable 2024 pricing model (see ADR-012)
```

---

## 8. Monorepo Best Practices (if applicable)

```
root/
  CLAUDE.md              ← global context
  packages/
    shared-types/        ← shared domain types
      CLAUDE.md          ← module context
    invoice-service/
      CLAUDE.md
    payment-service/
      CLAUDE.md
    api-gateway/
      CLAUDE.md
  docs/
    adr/
    ARCHITECTURE.md
    GLOSSARY.md
```

- Each package/service has its own `CLAUDE.md`
- Shared types live in a dedicated package
- Root `CLAUDE.md` explains the inter-service relationships
- Use workspace tooling (npm workspaces, Gradle composite builds, Poetry workspaces)

---

## 9. Anti-Patterns to Avoid

| Anti-Pattern | Why It Hurts AI Agents | Fix |
|---|---|---|
| God files (2000+ lines) | Agent loses context window, can't reason about the whole file | Split by responsibility |
| Deep indirection (5+ layers for simple CRUD) | Agent can't find where logic lives | Flatten unless complexity justifies layers |
| Stale/lying comments | Agent trusts comments and makes wrong decisions | Delete outdated comments; treat comments as code in review |
| Generated files in repo (without marking) | Agent may try to modify generated code | Add to `.gitignore` or mark with `@generated` header |
| Circular dependencies | Agent can't determine safe modification order | Enforce acyclic dependency rules |
| Magic strings/numbers | Agent can't understand intent | Extract to named constants or enums |
| Implicit conventions | Agent can't discover rules that only exist in team members' heads | Write them down in CLAUDE.md |

---

## 10. Continuous Maintenance

### Keep Meta Files Updated
- Add `CLAUDE.md` review to PR checklist
- When you add a module, add its `CLAUDE.md`
- When you make an architectural decision, write an ADR
- When you introduce a new convention, update the root `CLAUDE.md`

### Automated Validation
- Lint for file length limits
- CI check that every package has a `CLAUDE.md`
- Schema validation for OpenAPI/AsyncAPI specs
- Architectural fitness functions (e.g., ArchUnit for Java) to enforce boundaries

### Agent Feedback Loop
When an AI agent misunderstands your codebase and produces incorrect output:
1. Identify what context was missing
2. Add that context to the relevant `CLAUDE.md` or documentation
3. This iterative process continuously improves agent effectiveness

---

## Quick Start Checklist

When starting a new project, create these files **before writing any application code**:

- [ ] `CLAUDE.md` — project overview, tech stack, build commands, conventions
- [ ] `docs/ARCHITECTURE.md` — system diagram in Mermaid
- [ ] `docs/adr/001-initial-architecture.md` — why you chose this stack/structure
- [ ] `docs/GLOSSARY.md` — domain terms (even if short initially)
- [ ] `.env.example` — all configuration documented
- [ ] Domain-driven directory structure scaffolded
- [ ] CI pipeline with tests, linting, type checking

This upfront investment of ~1 hour pays for itself within the first week of AI-assisted development.
