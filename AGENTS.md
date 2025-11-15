# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project-Specific Patterns (Non-Obvious)

### API Data Fetching
- Pendle API calls have built-in retry logic with 160ms + random delay between requests
- Transaction data fetching caps at 8 pages (~8000 records) to prevent API abuse
- Client-side deduplication is mandatory - transaction IDs are tracked in a Set to prevent duplicates
- API pagination uses hybrid approach: `skip` for sequential requests, `resumeToken` for cursor-based pagination
- Transaction interface includes optional `impliedApy` and `valuation` properties for DeFi calculations

### Custom Error Handling
- All Pendle API errors should throw `PendleApiError` (extends `ApiError`) rather than generic Error
- Error patterns preserve original error status and code properties when wrapping

### TypeScript Build Configuration
- TypeScript project references: `tsconfig.json` references both `tsconfig.app.json` and `tsconfig.node.json`
- Build artifacts stored in `node_modules/.tmp/tsconfig.app.tsbuildinfo` for caching
- Use `@/*` path aliases (configured in both main and app tsconfig files)

### Testing Setup
- No testing framework configured - `npm run` shows no test scripts
- Testing approach undefined - requires setup if tests needed

## Build Commands

- **Development**: `npm run dev`
- **Build**: `npm run build` (TypeScript compilation then Vite build)
- **Linting**: `npm run lint`
- **Preview**: `npm run preview`