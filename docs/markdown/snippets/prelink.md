## Add support for prelinked static libraries

The static library gains a new `prelink` keyword argument that can be
used to prelink object files in that target. This is mostly useful in
embedded projects.