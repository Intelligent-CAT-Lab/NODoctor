project=$1
sha=$2
cloneDir=$3 #abs path
file_path=$4

mainDir=${cloneDir}

cd ${mainDir}/${sha}/${project}
echo "git checkout" ${file_path}
git checkout ${file_path}