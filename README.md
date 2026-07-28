# vcpkg2apt

Generate a `Dockerfile` that installs, via `apt`, the equivalents of the
dependencies declared in a `vcpkg.json` manifest — so your C++ Docker builds
stop re-installing (or re-compiling) the same dependencies every time.

## Why
 
vcpkg builds most ports from source by default, which is slow, and it's easy
to break Docker's layer cache if the `apt-get` / `vcpkg install` / `COPY`
steps aren't ordered carefully. By switching to prebuilt `apt` packages from
Ubuntu/Debian, the base image builds once and stays fast — no vcpkg build
step in your application's Docker build at all.