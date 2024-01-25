project=$1
sha=$2
test=$3
module=$4
cloneDir=$5
tag=$6
times=$3

timeStamp=$(echo -n $(date "+%Y-%m-%d %H:%M:%S") | shasum | cut -f 1 -d " ")

mkdir -p ./output_run_id/verify_patches_nondex_logs/${project}_${sha}/${test}/${tag}

mainDir=${cloneDir}
curDir=$(pwd)
logDir=$(pwd)/output_run2/verify_patches_nondex_logs/${project}_${sha}/${test}/${tag}

run_test(){
    mvn edu.illinois:nondex-maven-plugin:2.1.1:nondex -pl ${module} -Dtest=${test} -Dbasepom.check.skip-prettier -Dgpg.skip -Dfindbugs.skip=true -Drat.skip -Dcheckstyle.skip -Denforcer.skip=true -Dspotbugs.skip -Dmaven.test.failure.ignore=true -Djacoco.skip -Danimal.sniffer.skip -Dmaven.antrun.skip -Dfmt.skip -Dskip.npm -Dlicense.skipCheckLicense -Dlicense.skipAddThirdParty=true -Dfindbugs.skip -Dlicense.skip -Dskip.npm -Dskip.yarn -Dskip.bower -Dskip.grunt -Dskip.gulp -Dskip.jspm -Dskip.karma -Dskip.webpack -DskipDockerBuild -DskipDockerTag -DskipDockerPush -DskipDocker -Denforcer.skip -DnondexRuns=3 |&tee ${logDir}/"$1".log #--log-file
}

echo "* "STARTING at $(date) 
echo "* "LOG at ${logDir}
echo "* "RUNNING NonDex on ID tests
echo "* "REPO VERSION $(git rev-parse HEAD)

# echo ${mainDir}/${sha}/${project}
cd ${mainDir}/${sha}/${project}
java_version="$(grep "<jdk.*>" pom.xml)"
if [[ $java_version == *"11"* ]]; then
    echo "java version 11"
    export JAVA_HOME=/usr/lib/jvm/java-1.11.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
elif [[ $java_version == *"8"* ]]; then
    echo "java version 8"
    export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
elif [[ $java_version == *"1.8"* ]]; then
    echo "java version 8"
    export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
else
    # echo "java version:" $java_version
    export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
fi

echo "* "CURRENT DIR $(pwd)
for i in {1..${times}}
do
    run_test ${i}
done

cd ${curDir}
echo "* "ENDING at $(date)