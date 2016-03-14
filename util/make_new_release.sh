#! /bin/bash


function get_new_tag {
	local last_tag=$(git tag | tail -n 1 | tr -d '.')
	local next_tag=$(( 10#$last_tag + 1 ))

	if test $next_tag -lt 100; then
		next_tag=0$next_tag
	fi

	echo $next_tag | sed -E 's@([0-9])([0-9])([0-9])@\1.\2.\3@'
}

function add_git_tag {
	local new_tag=$1
	local commit_hash=$(git log --no-decorate -n 1 | head -n 1 | awk '{ print $2 }')
	git tag $new_tag $commit_hash -m "Creating a new version ${new_tag}"
}

function main {
	local target_dir="$1"

	local uncommited_files=$(git status --short --untracked-files=no | wc -l)

	if test $uncommit_files -gt 0; then
		echo "Uncommited files present, aborting the making of a new release"
		exit 1;
	fi

	# run pylint

	local new_tag=$(get_new_tag)
	local release_dir="$(basename ${PWD})-${new_tag}"

	# update release notes and edit release notes 
	./util/create_release_notes.sh $new_tag
	emacs --no-window-system ./release/RELEASE_NOTES.txt 

	# git tag 
	add_git_tag $new_tag

	# create version files (ver/version.txt)
	./util/create_release_bundle.sh ${target_dir} ${new_tag}

	#tarup and copy into /p/swamp/releases
	(
		cd $target_dir
		tar -c -z -f "${release_dir}.tar.gz" "${release_dir}"
		if test $? -eq 0; then
			scp "${release_dir}.tar.gz" vamshi@rydia.cs.wisc.edu:/p/swamp/releases
		fi
	)

}

main $@
