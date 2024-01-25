project=$1
sha=$2
cloneDir=$3 #abs path

mainDir=${cloneDir}


cd ${mainDir}/${sha}/${project}
echo "git stash"
git stash