project=$1
sha=$2
cloneDir=$3 #abs path

cd ${cloneDir}/${sha}/${project}
echo "git stash"
git stash