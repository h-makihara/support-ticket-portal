# React 19 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the frontend from React 18 to the current stable React 19 release without changing application behavior.

**Architecture:** Keep the existing Vite and `createRoot` application architecture. Update the React runtime and type packages, the npm lockfile, and the README technology label, then apply only the minimal TypeScript and type-declaration changes required by verification; preserve runtime behavior.

**Tech Stack:** React 19.2.8, React DOM 19.2.8, TypeScript 5.6, Vite 8, Vitest 4, npm 11

## Global Constraints

- Update `react` and `react-dom` to `^19.2.8`.
- Update `@types/react` to `^19.2.18` and `@types/react-dom` to `^19.2.4`.
- Update TypeScript to `~5.6.3`, the smallest stable release line supporting the existing `noUncheckedSideEffectImports` option.
- Do not upgrade unrelated dependencies or refactor application code.
- Do not use `--force` or `--legacy-peer-deps`.
- Keep all existing frontend behavior unchanged.

---

## File Structure

- Modify `frontend/package.json`: declare the React 19 runtime and type dependency ranges.
- Modify `frontend/package-lock.json`: record the npm-resolved React 19 dependency graph.
- Create `frontend/src/vite-env.d.ts`: load Vite's declarations for side-effect CSS imports.
- Modify `frontend/src/pages/TicketCreate.tsx`: use React 19's submit event type for the form handler.
- Modify `README.md`: identify the frontend as React 19.

### Task 1: Upgrade and Verify React 19

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `README.md:22`
- Test: existing tests under `frontend/src/**/*.test.ts` and `frontend/src/**/*.test.tsx`

**Interfaces:**
- Consumes: the existing Vite entry point using `ReactDOM.createRoot` in `frontend/src/main.tsx`.
- Produces: an npm dependency graph whose direct React runtime and type packages all use major version 19.

- [x] **Step 1: Capture the pre-migration dependency baseline**

Run:

```bash
cd frontend
npm ls react react-dom @types/react @types/react-dom --depth=0
```

Expected: the command reports React, React DOM, and both type packages at major version 18. This is the configuration-change equivalent of the failing baseline: it demonstrates that the repository does not yet meet the React 19 requirement.

- [x] **Step 2: Install the exact React 19 dependency ranges**

Run:

```bash
cd frontend
npm install --save-exact=false react@^19.2.8 react-dom@^19.2.8
npm install --save-dev --save-exact=false @types/react@^19.2.18 @types/react-dom@^19.2.4
```

Expected: npm updates `package.json` and `package-lock.json` without peer-dependency errors and without changing unrelated direct dependency declarations.

- [x] **Step 3: Update the documented frontend version**

Change this row in `README.md`:

```markdown
| Frontend | React 18 / TypeScript / Vite / nginx | http://localhost:3001 |
```

to:

```markdown
| Frontend | React 19 / TypeScript / Vite / nginx | http://localhost:3001 |
```

- [x] **Step 4: Verify the installed dependency majors and direct declarations**

Run:

```bash
cd frontend
npm ls react react-dom @types/react @types/react-dom --depth=0
npm pkg get dependencies.react dependencies.react-dom devDependencies.@types/react devDependencies.@types/react-dom
```

Expected: resolved runtime packages are `19.2.8`, resolved type packages are `19.2.18` and `19.2.4`, and all four direct declaration ranges begin with `^19.2`.

- [x] **Step 5: Run the frontend unit tests**

Run:

```bash
cd frontend
npm test
```

Expected: all Vitest tests pass without React compatibility warnings or errors.

- [x] **Step 6: Run explicit TypeScript validation**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exit status 0 with no type errors.

- [x] **Step 7: Build the production frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: Vite finishes successfully and creates the production bundle without React compatibility warnings or errors.

- [x] **Step 8: Check the React migration diff**

Run:

```bash
git diff --check
git diff -- README.md frontend/package.json frontend/package-lock.json
git status --short
```

Expected: the migration changes are limited to direct dependency declarations, their resolved lockfile graph, and the README label; `git diff --check` reports no whitespace errors. Commit after Task 2 restores the required type-checking gate.

### Task 2: Restore Explicit TypeScript Validation

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/vite-env.d.ts`
- Modify: `frontend/src/pages/TicketCreate.tsx:1,29`

**Interfaces:**
- Consumes: React 19's `SubmitEvent<T>` synthetic event type and the existing `noUncheckedSideEffectImports` compiler option.
- Produces: a form submit handler assignable to React 19's `SubmitEventHandler<HTMLFormElement>` and a TypeScript compiler that recognizes the existing project configuration.

- [x] **Step 1: Verify the two type-checking failures**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: FAIL with TS2322 for `TicketCreate`'s native `Event` handler and TS5023 for `noUncheckedSideEffectImports` under TypeScript 5.5.4.

- [x] **Step 2: Upgrade to the minimum compatible TypeScript release line**

Run:

```bash
cd frontend
npm install --save-dev 'typescript@~5.6.3'
npx tsc --noEmit
```

Expected: TypeScript resolves to 5.6.3, TS5023 disappears, TS2307 identifies the previously unchecked CSS side-effect import, and TS2322 remains. This isolates and verifies the compiler configuration fix.

- [x] **Step 3: Load Vite's client-side import declarations**

Create `frontend/src/vite-env.d.ts` with:

```ts
/// <reference types="vite/client" />
```

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: TS2307 for the existing CSS import disappears and only the form handler's TS2322 remains.

- [x] **Step 4: Use React 19's submit event type**

Change the React import and handler declaration in `frontend/src/pages/TicketCreate.tsx` to:

```tsx
import { useEffect, useState, type SubmitEvent } from 'react'

const handleSubmit = async (e: SubmitEvent<HTMLFormElement>) => {
```

- [x] **Step 5: Verify explicit type checking is green**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exit status 0 with no type errors.

- [x] **Step 6: Re-run behavioral and production verification**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: all 22 unit tests pass and Vite creates the production bundle without React compatibility warnings or errors.

- [x] **Step 7: Review and commit the complete migration**

Run:

```bash
git diff --check
git status --short
git diff -- README.md frontend/package.json frontend/package-lock.json frontend/src/vite-env.d.ts frontend/src/pages/TicketCreate.tsx docs/superpowers/specs/2026-08-17-react-19-migration-design.md docs/superpowers/plans/2026-08-17-react-19-migration.md
git add README.md frontend/package.json frontend/package-lock.json frontend/src/vite-env.d.ts frontend/src/pages/TicketCreate.tsx docs/superpowers/specs/2026-08-17-react-19-migration-design.md docs/superpowers/plans/2026-08-17-react-19-migration.md
git commit -m "chore: upgrade frontend to React 19"
```

Expected: the implementation and updated plan are committed together after every verification gate passes.
