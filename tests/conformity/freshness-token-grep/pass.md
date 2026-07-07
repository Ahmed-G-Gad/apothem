# Apothem

Apothem reads one shared profile and materializes harness-native configuration
for every registered harness. Run `apothem install` to write the configs and
`apothem verify` to confirm they are in place.

The profile lives at `~/.config/apothem/profile.yaml`. Edit it once; every
harness picks up the change on the next install. The placeholder identity in a
fresh profile is replaced by your own name, email, and handle before you ship.
