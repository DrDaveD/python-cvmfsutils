# Building python-cvmfsutils

## Development Setup

This project uses [pixi](https://pixi.sh) for environment management:

```bash
# Install dependencies
pixi install

# Run tests
pixi run test

# Generate RPM spec file
pixi run generate-spec
```

## Version Management

The project uses two version sources:

1. **Python package version**: `setuptools-scm` derives the version from git tags
2. **RPM spec version**: Extracted from the first changelog entry in `rpm/python-cvmfsutils.spec.in`

## RPM Packaging

### Spec File Generation

The RPM spec file is generated from a template to avoid external macros in the OpenSUSE Build System (OBS):

- **Template**: `rpm/python-cvmfsutils.spec.in` contains `@VERSION@` placeholders
- **Generator**: `generate_spec.py` extracts the version from the first changelog entry
- **Output**: `rpm/python-cvmfsutils.spec` is the generated file (checked into git for OBS)

The changelog is the single source of truth for the RPM version.

### Release Workflow

1. Update the changelog in `rpm/python-cvmfsutils.spec.in` with the new version:
   ```
   %changelog
   * Wed Jan 29 2026 Your Name <email@example.com> - 0.6.0-1
   - Release notes here
   ```

2. Regenerate the spec file:
   ```bash
   pixi run generate-spec
   ```

3. Commit both files, tag, and release:
   ```bash
   git add rpm/python-cvmfsutils.spec.in rpm/python-cvmfsutils.spec
   git commit -m "release: 0.6.0"
   git tag v0.6.0
   git push --tags
   ```

### CI/CD Integration

The GitHub Actions workflows automatically:

1. Verify the checked-in spec matches the generated output
2. Build RPMs for AlmaLinux 8/9 and openSUSE Leap/Tumbleweed
3. Test installation and functionality
4. Publish to PyPI on release

### OpenSUSE Build System (OBS) Compatibility

The generated spec file works with OBS without requiring external macros:

- No `%{version}` macro usage - version is embedded directly
- Spec file is checked into git so OBS can read it
- Template-based generation ensures consistency

## Package Structure

- **Source layout**: Code is in `src/cvmfs/` following modern Python packaging standards
- **Console scripts**: Utilities are defined as entry points in `setup.cfg`
- **Dependencies**: Declared in `setup.cfg` with appropriate version constraints

## Testing

CI tests across multiple platforms:

- **Python versions**: 3.8-3.12
- **Operating systems**: Ubuntu, macOS (Intel/ARM)
- **RPM builds**: AlmaLinux 8/9, openSUSE Leap 15.5/15.6, openSUSE Tumbleweed

Local testing:

```bash
# Run test suite
pixi run test

# Test RPM spec generation
pixi run generate-spec
```
