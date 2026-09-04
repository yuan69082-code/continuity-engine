# Independent probe helper error (not an Engine failure)

The first invocation ran 2 test methods in 0.077 seconds and had 4 helper errors.
Both lowercase reserved-directory checks passed. The uppercase subtests failed in
test setup with FileExistsError / WinError 183 before invoking the fixture: their
synthetic owner directory names differed only in case, and Windows treated each
pair as the same directory. Original repositories were not modified.

The helper was corrected to use a numeric case index in owner paths, preserving
all assertions. Original scratch directory remains available:
`C:\Users\Administrator\AppData\Local\Temp\p10r2-independent-6dz6rse3`.

This helper error is separate from any subsequent product-test result.
