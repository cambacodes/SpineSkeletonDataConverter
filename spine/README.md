# Vendored Spine runtimes

The runtime source trees in this directory are retained as version-specific
format references. They are compiled for syntax validation by CMake, but the
converter executable uses the neutral data model and readers/writers under
`src/`.

The two legacy additions are reproducible snapshots from the official
Esoteric Software repository:

| Directory | Upstream revision | Declared/export version |
| --- | --- | --- |
| `spine-c-33` | `eb540387e6346c9c9247a9f4826538e2a3e6e53b` | 3.3.07 |
| `spine-c-34` | tag `3.4.02` (`ef5013143178918ddfc7cabfbddeae7aec7cf84e`) | 3.4.02 |

Source: <https://github.com/EsotericSoftware/spine-runtimes>

Only each snapshot's `include/spine`, `src/spine`, `README.md`, and `LICENSE`
are vendored. Source files are otherwise unchanged, apart from normalized LF
line endings in the 3.4 snapshot. The licenses within each directory govern
the corresponding Spine Runtime source.
