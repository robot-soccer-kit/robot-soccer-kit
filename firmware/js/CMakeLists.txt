cmake_minimum_required(VERSION 2.8)
project(metabot)

option (JS "JavaScript mode" ON)

# Directories
set (BASE "${CMAKE_SOURCE_DIR}/..")
set (RH_BASE "${BASE}/Maple/LibRhoban/")
set (RHOCK_BASE "${BASE}/Maple/Rhock/src")
file (STRINGS "${BASE}/version" VERSION)

# Includes
include_directories (${RHOCK_BASE} ${RH_BASE})

# Sources
set (SOURCES
    ${BASE}/odometry.cpp
    ${BASE}/leds.cpp
    ${BASE}/js_utils.cpp
    ${BASE}/dc.cpp
    ${BASE}/imu.cpp
    ${BASE}/buzzer.cpp
    ${BASE}/motion.cpp
    ${BASE}/opticals.cpp
    ${BASE}/distance.cpp
    ${BASE}/rhock-functions.cpp
    ${BASE}/rhock-stream.cpp
    ${RH_BASE}/function.cpp
    )

# Building rhock
add_subdirectory ("${RHOCK_BASE}" rhock)

# Compilation options
set(CMAKE_C_COMPILER emcc)
set(CMAKE_CXX_COMPILER em++)
set(CMAKE_AR emar)
set(CMAKE_RANLIB emranlib)
set(CMAKE_C_FLAGS -g)
set(CMAKE_CXX_FLAGS -g)
set (CMAKE_C_FLAGS "--minify 0 -Os -std=c99 -Wall -U__STRICT_ANSI__ -Wno-warn-absolute-paths")
set (CMAKE_CXX_FLAGS "--minify 0 -Os --bind -Wall -Wno-reorder -pedantic -U__STRICT_ANSI__ -Wno-warn-absolute-paths -s DISABLE_EXCEPTION_CATCHING=0 -DMETABOT_VERSION=${VERSION}")

add_definitions (-DRHOCK_NATIVE_SYMBOLS -DRHOCK)

# Produce the module
add_executable (module.js ${SRC_METABOT} ${RHOCK_JS} ${SOURCES})

add_custom_target (module.min.js
    COMMAND uglifyjs module.js > module.min.js
    DEPENDS module.js
    )

add_custom_target (module.tgz
    COMMAND tar zcvf module.tgz module.min.js
    DEPENDS module.min.js
    )
