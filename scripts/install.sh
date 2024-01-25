input=$1 #project_url
cloneDir=$2 # dir to clone all projects

timeStamp=$(echo -n $(date "+%Y-%m-%d %H:%M:%S") | shasum | cut -f 1 -d " ")

mkdir -p ./output/$timeStamp/install_logs

mainDir=$(pwd)/${cloneDir}
logDir=$(pwd)/output/$timeStamp/install_logs

exec 3>&1 4>&2
trap $(exec 2>&4 1>&3) 0 1 2 3
exec 1>$logDir/$timeStamp.log 2>&1

install(){
    t=$(echo -n $(date "+%Y-%m-%d %H:%M:%S") | shasum | cut -f 1 -d " ")
    mvn install -pl ${module} -am -DskipTests -Dfindbugs.skip=true -Dbasepom.check.skip-prettier -Dgpg.skip -Drat.skip -Dskip.npm -Dskip.yarn -Dskip.bower -Dskip.grunt -Dskip.gulp -Dskip.jspm -Dskip.karma -Dskip.webpack -Dcheckstyle.skip -Denforcer.skip=true -Dspotbugs.skip -Dmaven.test.failure.ignore=true -Djacoco.skip -Danimal.sniffer.skip -Dmaven.antrun.skip -Dfmt.skip -Dskip.npm -Dlicense.skipCheckLicense -Dlicense.skipAddThirdParty=true -Dfindbugs.skip -Dlicense.skip -DskipDockerBuild -DskipDockerTag -DskipDockerPush -DskipDocker -Denforcer.skip |&tee install${project}${t}.log
    res="$(grep 'BUILD ' ${mainDir}/${sha}/${project}/install${project}${t}.log)"
    echo "build-result:" ${project} ${sha} ${module} ${res}
    #mvn install -pl ${module} -am -DskipTests --log-file install_${project}.log
}

for info in $(cat $input); do
    url=$(echo $info | cut -d, -f1)
    sha=$(echo $info | cut -d, -f2)
    module=$(echo $info | cut -d, -f3)
    project=${url##*/}

    cd ${mainDir}/${sha}/${project}
    echo ${mainDir}/${sha}/${project}
    echo "run git stash"
    git stash
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
    elif [[ $url == "https://github.com/INRIA/spoon" ]]; then
        echo "java version 11"
        export JAVA_HOME=/usr/lib/jvm/java-1.11.0-openjdk-amd64
        export PATH=$JAVA_HOME/bin:$PATH
    elif [[ $project == "cloudstack" ]]; then
        echo "java version 11"
        export JAVA_HOME=/usr/lib/jvm/java-1.11.0-openjdk-amd64
        export PATH=$JAVA_HOME/bin:$PATH
    else
        echo "java version not found, will use 8" $java_version
        export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64
        export PATH=$JAVA_HOME/bin:$PATH
    fi

    
    install

    cd ../../..
    done