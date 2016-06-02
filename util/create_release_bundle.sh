#! /bin/bash

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
	return 0
	
	for other_plat in $(cat ~/bin/resources/all_platforms.txt | fgrep -v "$main_plat" ); do
		mkdir -p $dest_dir/$other_plat/{in-files,swamp-conf}

		for sub_dir in in-files swamp-conf; do
			(
				cd $dest_dir/$other_plat/$sub_dir
				find ../../$main_plat/$sub_dir -type f -exec ln -s '{}' ';'
			)
		done
	done

	for plat in $(cat ~/bin/resources/all_platforms.txt); do
		local rvm="$PWD/ruby-binaries/ruby-binary---$plat/rvm.tar.gz"
		[[ -f "$rvm" ]] && cp "$rvm" "$dest_dir/$plat/in-files"
	done

}

function copy_scripts {

	local dest_dir="$1"
    local release_dir="$PWD/release"

	[[ -d "$release_dir/swamp-conf" ]] && \
		cp -r "$release_dir/swamp-conf" "$dest_dir"

	local NODEJS=$(find $HOME/p/swamp/frameworks/node.js/noarch -name 'node-v?.?.?-linux-x64.tar.xz' | sort | tail -n 1)
	local PHP_COMPOSER=$(find $HOME/p/swamp/frameworks/php/noarch -name 'composer.phar' | sort | tail -n 1)

    cp -r "$release_dir/in-files" "$dest_dir"
	cp -r "$NODEJS" "$dest_dir/in-files"
	cp -r "$PHP_COMPOSER" "$dest_dir/in-files"

	local scripts_dir="$dest_dir/in-files/scripts"
	mkdir -p "$scripts_dir"

	#cp -r "$PWD/bin" $scripts_dir
	
	local lib_dir="$scripts_dir/lib"
	mkdir -p "$lib_dir"

	cp -r $PWD/lib/* "$lib_dir"

	local ruby_assess_dir="$lib_dir/js_assess"
	mkdir $ruby_assess_dir
	cp -r $PWD/src/* $ruby_assess_dir

	local version_dir="$lib_dir/version"
	mkdir -p $version_dir
	echo $new_version > $version_dir/version.txt
	echo '' > $version_dir/__init__.py

	(
		cd "$(dirname $scripts_dir)"
		tar -c -z --file="$(basename $scripts_dir)"".tar.gz" "$(basename $scripts_dir)"
		if test $? -eq 0; then
			rm -rf "$(basename $scripts_dir)"
		fi
	)
}

if test $# -ne 2; then
    echo "need a destination directory and a version an argument"
    exit 1
fi

main $@

