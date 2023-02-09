#!/usr/bin/env bash

set -eou pipefail
set -x

output_id="$1"
output="test-assets/output_$output_id"
rm -rf "$output"
mkdir "$output"

test_paths=(
	"/openedx/edx-platform"
	"/openedx/staticfiles"
	"/openedx/themes"
)

test_mode ( ) {
	mode="$1"
	mkdir "$output/$mode"
	for path in "${test_paths[@]}" ; do 
		outpath="$output/${mode}${path}"
		mkdir -p "$(dirname "$outpath")"
		tutor "$mode" copyfrom lms "$path" "$outpath"
	done
}


tutor config save \
	--set EDX_PLATFORM_REPOSITORY=https://github.com/kdmccormick/edx-platform \
	--set EDX_PLATFORM_VERSION=kdmccormick/assets-build-sh
tutor images build openedx
tutor dev dc build lms
test_mode local
test_mode dev
#test_mode k8s # TODO

