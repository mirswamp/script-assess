#!/bin/bash

function main {
	
	local GIT_TAG=$1
	local FILENAME="$PWD/release/RELEASE_NOTES.txt"
	
	if test -f "${FILENAME}"; then
		if test "$(uname -s)" == "Darwin"; then
			MTIME="$(stat -f '%m' ${FILENAME})"
		elif  test "$(uname -s)" == "Linux"; then
			MTIME="$(stat --format='%Y' ${FILENAME} )"
		fi
		
		if test $# -gt 1; then
			NEW_FILENAME="temp_release_notes.txt"
			#NEW_FILENAME="/dev/stdout"
		else
			NEW_FILENAME="temp_release_notes.txt"
		fi

		if test "$(git log --since=${MTIME} --pretty=fuller --format='%B')" != ""; then
			SEP=$(python3 -c "print('-'*35)")
			cat > "${NEW_FILENAME}" <<EOF
${SEP}
ruby-assess version ${GIT_TAG} ($(date))
${SEP}
$(git log --since=${MTIME} --pretty=fuller --format='%B' | sed -E 's:.+:- &:')

$(cat ${FILENAME})
EOF

		if test "${NEW_FILENAME}" != "/dev/stdout" -a -f "${NEW_FILENAME}"; then
			mv "${NEW_FILENAME}" "${FILENAME}"
    	fi
		fi
	fi

}


: ${1:?"Usage: $0 <release-tag>"}

main $@
