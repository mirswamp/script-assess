#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Need a Directory as an argument to copy the files into"
    exit 1
fi

function main {

    local dest_dir=${1}
    if [ ! -d "${dest_dir}" ]; then
		mkdir -p "${dest_dir}"
    fi

    (
		local scripts_dir="${dest_dir}/scripts"
		mkdir -p "${scripts_dir}"

		#cp -r "${PWD}/resources" ${scripts_dir}
		#cp -r "${PWD}/build-monitors" ${scripts_dir}
		#cp -r "${PWD}/build-sys" ${scripts_dir}
		cp -r "${PWD}/bin" ${scripts_dir}
		
		local lib_dir="${scripts_dir}/lib"
		mkdir -p $lib_dir
		cp -r ${PWD}/lib/* $lib_dir

		local ruby_assess_dir=${lib_dir}/ruby_assess
		mkdir -p ${ruby_assess_dir}
		cp -r ${PWD}/src/* ${ruby_assess_dir}

		(
			cd "$(dirname ${scripts_dir})"
			tar -c -z --file="$(basename ${scripts_dir})"".tar.gz" "$(basename ${scripts_dir})"
			if test $? -eq 0; then
				rm -rf "$(basename ${scripts_dir})"
			fi
		)
    )
}

main $@
