# Interactive Frame Format

Frames exchanged during an interactive simulation are YAML documents with the following structure:

```yaml
simulation:
  inputs:
    <key>: <value>
```

The `inputs` section contains key/value pairs that are provided to the MATLAB simulation. Each frame sent from the message broker to the agent should conform to this format.
