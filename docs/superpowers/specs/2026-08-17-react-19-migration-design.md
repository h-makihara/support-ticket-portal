# React 19 Migration Design

## Goal

Adopt React 19 for the frontend while preserving the application's existing behavior and keeping the migration scope limited to React-related dependencies, documentation, and the minimal type-checking compatibility fixes revealed during verification.

## Changes

- Update `react` and `react-dom` from React 18 to the latest compatible React 19 releases.
- Update `@types/react` and `@types/react-dom` to their React 19 release lines so TypeScript uses matching APIs.
- Regenerate `frontend/package-lock.json` with the repository's declared npm version.
- Update the root README technology summary from React 18 to React 19.
- Update TypeScript to the smallest stable release line that supports the existing compiler options.
- Add Vite's standard client declarations and use React 19's submit event type so explicit type checking succeeds without changing runtime behavior.
- Avoid unrelated dependency upgrades and application refactoring.

## Compatibility Strategy

The current frontend already uses `createRoot`, the automatic JSX runtime, and React-compatible versions of Vite, the React Vite plugin, Testing Library, and React Router. No source changes are planned unless verification identifies a concrete React 19 incompatibility.

If npm reports an incompatible peer dependency, update only the package directly blocking React 19 and document why. Do not bypass peer-dependency checks with `--force` or `--legacy-peer-deps`.

## Verification

Run the frontend unit test suite and production build after installing the updated dependency graph. The build provides TypeScript checking through Vite's existing workflow only to the extent currently configured; therefore also run TypeScript directly with `tsc --noEmit` to validate React 19 type compatibility.

Success means:

- The lockfile resolves `react` and `react-dom` to React 19.
- React type packages resolve to version 19.
- Unit tests pass.
- TypeScript validation passes.
- The production build succeeds without React compatibility warnings or errors.

## Testing Approach

This migration changes dependency metadata, documentation, and type-only compatibility declarations rather than introducing application behavior. A new failing application test would not meaningfully prove the dependency version, so implementation will use the existing behavioral tests plus dependency-version inspection, red-green TypeScript validation, and a production build instead of adding a synthetic runtime test.
