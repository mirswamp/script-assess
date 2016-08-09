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

p_swamp=/p/swamp/frameworks

## hack for vamshi's laptop environment
if [ ! -d $p_swamp ] ; then
	p_swamp=$HOME/$p_swamp
	echo $p: adjusting /p/swamp for vamshi
fi

update_platform=$p_swamp/platform/update-platform

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

function main {

	#local framework="$(basename $PWD)"
	local framework="script-assess"
	local new_version="$2"
    local dest_dir="$1/$framework-$new_version"

	local main_plat="noarch"

    [[ ! -d "$dest_dir/$main_plat" ]] && mkdir -p "$dest_dir/$main_plat"

	copy_scripts "$dest_dir/$main_plat"
	cp $PWD/release/{LICENSE.txt,RELEASE_NOTES.txt} "$dest_dir"

	md5_sum "$dest_dir"
}

function copy_scripts {

	local dest_dir="$1"
    local release_dir="$PWD/release"

	[[ -d "$release_dir/swamp-conf" ]] && \
		cp -r "$release_dir/swamp-conf" "$dest_dir"

	FRAMEWORKS="/p/swamp/frameworks"

	if [[ ! -d "$FRAMEWORKS" ]]; then
		FRAMEWORKS="$HOME/$FRAMEWORKS"
	fi
	
	local NODEJS=$(find "$FRAMEWORKS/node.js/noarch" -name 'node-v?.?.?-linux-x64.tar.xz' | sort | tail -n 1)
	local PHP_COMPOSER=$(find "$FRAMEWORKS/php/noarch" -name 'composer.phar' | sort | tail -n 1)

	mkdir -p "$dest_dir/in-files"
    cp -r "$release_dir/in-files" "$dest_dir"
	cp -r "$NODEJS" "$dest_dir/in-files"
	cp -r "$PHP_COMPOSER" "$dest_dir/in-files"
	
	$update_platform --framework node.js  --dir "$dest_dir/in-files" || exit 1

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

