# React 19 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the frontend from React 18 to the current stable React 19 release without changing application behavior.

**Architecture:** Keep the existing Vite and `createRoot` application architecture. Change only the React runtime packages, their TypeScript definitions, the npm lockfile, and the README technology label; source code changes are allowed only if verification proves a specific React 19 incompatibility.

**Tech Stack:** React 19.2.8, React DOM 19.2.8, TypeScript 5.5, Vite 8, Vitest 4, npm 11

## Global Constraints

- Update `react` and `react-dom` to `^19.2.8`.
- Update `@types/react` to `^19.2.18` and `@types/react-dom` to `^19.2.4`.
- Do not upgrade unrelated dependencies or refactor application code.
- Do not use `--force` or `--legacy-peer-deps`.
- Keep all existing frontend behavior unchanged.

---

## File Structure

- Modify `frontend/package.json`: declare the React 19 runtime and type dependency ranges.
- Modify `frontend/package-lock.json`: record the npm-resolved React 19 dependency graph.
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

- [ ] **Step 1: Capture the pre-migration dependency baseline**

Run:

```bash
cd frontend
npm ls react react-dom @types/react @types/react-dom --depth=0
```

Expected: the command reports React, React DOM, and both type packages at major version 18. This is the configuration-change equivalent of the failing baseline: it demonstrates that the repository does not yet meet the React 19 requirement.

- [ ] **Step 2: Install the exact React 19 dependency ranges**

Run:

```bash
cd frontend
npm install --save-exact=false react@^19.2.8 react-dom@^19.2.8
npm install --save-dev --save-exact=false @types/react@^19.2.18 @types/react-dom@^19.2.4
```

Expected: npm updates `package.json` and `package-lock.json` without peer-dependency errors and without changing unrelated direct dependency declarations.

- [ ] **Step 3: Update the documented frontend version**

Change this row in `README.md`:

```markdown
| Frontend | React 18 / TypeScript / Vite / nginx | http://localhost:3001 |
```

to:

```markdown
| Frontend | React 19 / TypeScript / Vite / nginx | http://localhost:3001 |
```

- [ ] **Step 4: Verify the installed dependency majors and direct declarations**

Run:

```bash
cd frontend
npm ls react react-dom @types/react @types/react-dom --depth=0
npm pkg get dependencies.react dependencies.react-dom devDependencies.@types/react devDependencies.@types/react-dom
```

Expected: resolved runtime packages are `19.2.8`, resolved type packages are `19.2.18` and `19.2.4`, and all four direct declaration ranges begin with `^19.2`.

- [ ] **Step 5: Run the frontend unit tests**

Run:

```bash
cd frontend
npm test
```

Expected: all Vitest tests pass without React compatibility warnings or errors.

- [ ] **Step 6: Run explicit TypeScript validation**

Run:

```bash
cd frontend
npx tsc --noEmit
```

Expected: exit status 0 with no type errors.

- [ ] **Step 7: Build the production frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: Vite finishes successfully and creates the production bundle without React compatibility warnings or errors.

- [ ] **Step 8: Check the final diff and commit**

Run:

```bash
git diff --check
git diff -- README.md frontend/package.json frontend/package-lock.json
git status --short
git add README.md frontend/package.json frontend/package-lock.json docs/superpowers/plans/2026-08-17-react-19-migration.md
git commit -m "chore: upgrade frontend to React 19"
```

Expected: only the three migration files and this plan are included in the implementation commit; `git diff --check` reports no whitespace errors.
