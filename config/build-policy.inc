# Common defaults for every target; override in the target conf/edf-policy.conf.
SDKMACHINE = "x86_64"
SSTATE_MIRRORS = ""
BB_HASHSERVE_UPSTREAM = ""
BB_DISKMON_DIRS = "STOPTASKS,${TMPDIR},15G,100K STOPTASKS,${DL_DIR},15G,100K HALT,${TMPDIR},10G,50K HALT,${DL_DIR},10G,50K"
