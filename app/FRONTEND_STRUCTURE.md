# Frontend resources

`dist/index.html` contains the document skeleton. `dist/styles.css` contains the stylesheet. The complete, ordered resource list is `dist/assets.json`.

The application uses classic scripts and a shared **lexical** environment. Application names are `let`/`const` bindings, not properties written onto `window`. Each script retains strict mode. This preserves the original private application's name resolution without replacing native Window properties.

Load order matters:

1. The generated candidate-literature bundle provides reviewed evidence; `candidates.js` provides the standalone candidate data rules. The private external-research memo is not part of the public app or its offline bundle.
2. `js/bindings.js` declares the application's state, initially undefined as the original `var` bindings were.
3. `js/definitions/` contains named functions grouped by feature. All definitions load before initialization, preserving calls to functions originally declared later in the single IIFE.
4. `js/initialize/` contains the original state initialization and setup statements, grouped by feature. Loading these files only defines initializer functions.
5. `js/bootstrap.js` calls every initializer in the original order, in one synchronous stack. Timers, events and network completions cannot interleave between initialization resources.

The initial extraction retained function bodies and names. Later intentional behavior changes are recorded in the reviewed manifest revision. The original top-level functions were not reassigned, so their bindings can be `const`. Top-level `var` initializers become assignments to the already-declared lexical state. There were no outer `this`, `return` or nested outer `var` dependencies to migrate.

`scripts/inline-source-manifest.json` records the original extraction provenance and the current reviewed AST fingerprints. `scripts/verify-split.cjs` checks every current function and initialization statement, load order, strict mode, references, independent/combined syntax, lexical declarations and the 70 KB resource limit. It can also independently verify the original AST provenance against the complete pre-extraction HTML snapshot:

```sh
node --expose-internals scripts/verify-split.cjs --reference /path/to/original/index.html
```

The verifier uses Acorn bundled with Node 22, the CI version; no parser dependency is downloaded. The regular candidate test file invokes it automatically. Intentional behavior changes require updating the affected reviewed baseline fingerprints; the extraction comparison must not be silently disabled.

`scripts/split-inline.cjs` is the one-time extraction utility. It expects an original inline IIFE and deliberately refuses to re-extract the resulting shell. New resources must also be added to the ordered asset list, HTML references and service-worker offline shell.

The main header's **Login for team** link delegates sign-in and the destination's existing access checks to GitHub. The public app does not create a login session, detect team roles, fetch private notes, or change membership or repository permissions. The private notes remain owner-only; the label does not grant team access. Keep private contents and credentials outside the public app and its offline cache.
