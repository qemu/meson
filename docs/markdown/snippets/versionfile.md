## Project version can be specified with a file

Meson can be instructed to load project's version string from an
external file like this:

```meson
project('foo', 'c' version: files('VERSION'))
```

The version string would be set to the first line of the `VERSION`
file. Leading and trailing whitespace on the file is stripped.