- Follow http://source.android.com/source/building.html
- . build/envsetup.sh
- lunch aosp_arm-user

2013-09-26 - bulach - perf / perfhost / tcpdump:
git revert -n 93501d3 # issue with __strncpy_chk2
make -j32 perf perfhost tcpdump

