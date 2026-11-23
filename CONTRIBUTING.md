# Contributing

Add a small allowed/denied pair with a manually justified expected result, or a fake adapter contract case. Use newly authored synthetic data with clear publication rights. Include the profile version, input, expected/actual and reproduction command.

Run `python -m unittest discover -s tests -v` and `python -m clinic`. Keep the core offline and independent of external services. New wallet adapters require a threat model, effect-boundary description, scope/version contract and appropriate review; never include wallet keys or account data in cases.

Report harness behavior with a reproducer. This repository does not authorize testing attacks on third-party systems.
