projectDir=$1 #abs path

if [[ -d ${projectDir} ]]; then
    echo "* ${projectDir} does exist."
    cd ${projectDir}
    echo "* Git stash"
    git stash
else
    echo "* PWD ${pwd}"
    echo "* ${projectDir} does not exist."
fi