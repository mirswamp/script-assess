#! /bin/bash

p=`basename $0`

## Create a java-assess release.
## Must be run from root directory of java-assess workspace.

make_tarball=true
make_cksum=true

while [ $# -gt 0 ] ; do
    case $1 in
		--no-tar)
			make_tarball=false
			;;
		--no-ck)
			make_cksum=false
			;;
		--test)
			make_tarball=false
			make_cksum=false
			;;
		--swamp-root)
			p_swamp=$2
			shift
			;;
		-*)
			echo $p: $1: unkown optarg 1>&2
			exit 1
			;;
		*)
			break
			;;
    esac
    shift
done

if [ $# -lt 1  -o  $# -gt 2 ] ; then
    echo usage: $p dest-dir '[version]' 1>&2
    exit 1
fi

if [ -z "$p_swamp" ] ; then
	## CS
	p_swamp=/p/swamp
fi

if [ -n "$SWAMP_FRAMEWORK_DEPENDENCIES" ]; then
        if [ ! -d "$SWAMP_FRAMEWORK_DEPENDENCIES" ]; then
                echo "$p: SWAMP_FRAMEWORK_DEPENDENCIES set, but not a directory ($SWAMP_FRAMEWORK_DEPENDENCIES)" 1>&2
                exit 1
        fi
        ## SWAMP_FRAMEWORK_DEPENDENCIES overrides p_swamp & --swamp-root
        ## XXX all uses of p_swamp should be removed
        ## set p_swamp here, so the rest of script ignores it
        p_swamp=UNDEFINED_USING__SWAMP_FRAMEWORK_DEPENDENCIES__VAR
        p_swamp_fw=$SWAMP_FRAMEWORK_DEPENDENCIES
elif [ ! -d $p_swamp ] ; then
        echo $p: $p_swamp: swamp root dir missing 1>&2
        exit 1
else
        p_swamp_fw=${p_swamp}/frameworks
fi


## hack for vamshi's laptop environment ... safe in case it is useful
if false ; then
	if [ ! -d $p_swamp_fw ] ; then
	    p_swamp=$HOME/$p_swamp_fw
	    echo $p: adjusting /p/swamp for vamshi
	fi
fi

if [ ! -d "$p_swamp_fw" ] ; then
	echo $p: $p_swamp_fw: frameworks dir missing 1>&2
	exit 1
fi

update_platform=$p_swamp_fw/platform/update-platform

if [ ! -x $update_platform ] ; then
    echo $p: platform update tool missing/unusable 1>&2
    exit 1
fi

function md5_sum {

    local dest_dir="$1"

    (
		cd "$dest_dir"
		local checksumfile="md5sum"

		if test "$(uname -s)" == "Darwin"; then
			local MD5EXE="md5"
		elif test "$(uname -s)" == "Linux"; then
			local MD5EXE="md5sum"
		fi

		find . -type f ! -name "$checksumfile" -exec "$MD5EXE" '{}' ';' > "$checksumfile"
    )
}

function create_dir {
	local dir="$1";

    if [[ ! -d "$1" ]]; then
		mkdir -p "$1"
    else
		rm -rf "$1"/*
    fi
}

function create_links {
	local common="$1"
	local plat="$2"

	(
		cd $plat;
		for FILE in $(find $common -type f); do
			ln -s ../../common/in-files/$(basename $FILE)
		done
	)
}

function main {

    #local framework="$(basename $PWD)"
    local framework="script-assess-v2"
    local new_version="$2"
    local dest_dir="$1/$framework-$new_version"

    local main_plat="common"

    create_dir "$dest_dir/$main_plat"
    copy_scripts "$dest_dir/$main_plat"

	for plat in ubuntu-16.04-64; do
		create_dir "$dest_dir/$plat/in-files"
		cp "$p_swamp_fw/python/python-3-arch/$plat/python-3-bin.tar.gz"  "$dest_dir/$plat/in-files"
		cp "$p_swamp_fw/python/python-2-arch/$plat/python-2-bin.tar.gz"  "$dest_dir/$plat/in-files"
		create_links "$dest_dir/$main_plat/in-files" "$dest_dir/$plat/in-files"
	done
	cp $PWD/release/{LICENSE.txt,RELEASE_NOTES.txt} "$dest_dir"
    md5_sum "$dest_dir"
}

function copy_scripts {

    local dest_dir="$1"
    local release_dir="$PWD/release"

    [[ -d "$release_dir/swamp-conf" ]] && \
		cp -r "$release_dir/swamp-conf" "$dest_dir"

    FRAMEWORKS="$p_swamp_fw"

    if [[ ! -d "$FRAMEWORKS" ]]; then
		FRAMEWORKS="$HOME/$FRAMEWORKS"
    fi

    local NODEJS_x86_64=$(find "$FRAMEWORKS/node.js/noarch" -name 'node-v?.?.?-linux-x64.tar.xz' | sort | tail -n 1)
    local NODEJS_x86_32=$(find "$FRAMEWORKS/node.js/noarch" -name 'node-v?.?.?-linux-x86.tar.xz' | sort | tail -n 1)
    local PHP_COMPOSER=$(find "$FRAMEWORKS/php/noarch" -name 'composer.phar' | sort | tail -n 1)

    mkdir -p "$dest_dir/in-files"
    cp -r "$release_dir/in-files" "$dest_dir"
    [[ -n "$NODEJS_x86_64" ]] && cp -r "$NODEJS_x86_64" "$dest_dir/in-files"
    [[ -n "$NODEJS_x86_32" ]] && cp -r "$NODEJS_x86_32" "$dest_dir/in-files"
    cp -r "$PHP_COMPOSER" "$dest_dir/in-files"
    
    $update_platform --swamp-root ${p_swamp} --framework node.js  --dir "$dest_dir/in-files" || exit 1

    local scripts_dir="$dest_dir/in-files/scripts"
    mkdir -p "$scripts_dir"

	#cp -r "$PWD/bin" $scripts_dir
    
    local lib_dir="$scripts_dir/lib"
    mkdir -p "$lib_dir"

    cp -r $PWD/lib/* "$lib_dir"

    local script_assess_dir="$lib_dir/script_assess"
    mkdir $script_assess_dir
    cp -r $PWD/src/* $script_assess_dir

    local version_dir="$lib_dir/version"
    mkdir -p $version_dir
    echo $new_version > $version_dir/version.txt
    echo '' > $version_dir/__init__.py

    (
		cd "$(dirname $scripts_dir)"
		tar -c -z --file="$(basename $scripts_dir)"".tar.gz" "$(basename $scripts_dir)"
		if [[ $? -eq 0 ]]; then
			rm -rf "$(basename $scripts_dir)"
		fi
    )
}

if [[ $# -ne 2 ]]; then
	echo "need a destination directory and a version an argument"
	exit 1
fi

main $@

