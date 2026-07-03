깃허브 Private 저장소를 서버에서 `git pull` 할 수 있게 만드는 전체 흐름은

1. 서버(또는 CI 머신)에 **전용 SSH 키 쌍을 생성**하고
2. 그 공개키를 **해당 리포지토리의 Deploy key**로 등록한 뒤
3. 서버에 비밀키를 잘 배치하고 **SSH 접속 테스트 → git clone / git pull** 순으로 진행하는 것입니다.

아래를 그대로 따라 하시면 됩니다.

---

## 1. 서버에서 Deploy Key용 SSH 키 생성

Deploy key는 “서버 → GitHub” 단방향 인증에 쓰는 전용 SSH 키입니다.
GitHub 계정의 개인 키를 재사용하지 않고, **리포지토리마다 새 키**를 만드는 것을 권장합니다.

예: 리눅스 서버에 접속한 상태라고 가정합니다.

```bash
# ~/.ssh 폴더가 없다면 생성
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# deploy key 생성 (이름은 repo에 맞게 정하세요)
cd ~/.ssh
ssh-keygen -t ed25519 -C "deploy-key-for-onigiri-neo" -f id_ed25519_onigiri
```

* `-t ed25519` : 최신·간결한 키 타입
* `-C` : 주석(구분용)
* `-f` : 키 파일 이름
* **Passphrase는 비워두는 것**이 일반적인 Deploy key 패턴입니다 (그냥 엔터 두 번).

생성 후 파일:

* 비밀키: `~/.ssh/id_ed25519_onigiri`
* 공개키: `~/.ssh/id_ed25519_onigiri.pub`

---

## 2. 공개키를 GitHub 리포지토리 Deploy Key로 등록

1. 브라우저에서 GitHub 접속

2. 대상 Private 저장소로 이동 (예: `owner/my-private-repo`)

3. 상단 메뉴에서
   `Settings` → 왼쪽 메뉴에서 `Code and automation > Deploy keys` 선택

4. `Add deploy key` 버튼 클릭

5. 다음 항목 입력

   * **Title**: 예) `Prod server deploy key` 또는 `MyServer Pull Key`
   * **Key**: 서버에서 아래 명령으로 나온 내용 전체를 복사해서 붙여 넣습니다.

     ```bash
     cat ~/.ssh/id_ed25519_onigiri.pub
     ```
   * **Allow write access**

     * 단순히 `git pull`만 할 거라면 체크하지 마십시오 (read-only).
     * 서버에서 이 리포에 `git push`까지 해야 한다면 체크.

6. `Add key` 버튼으로 저장.

이제 GitHub 쪽 설정은 끝났습니다.

---

## 3. 서버의 SSH 설정 (비밀키 권한 및 ssh-config)

비밀키 권한을 안전하게 설정합니다.

```bash
chmod 600 ~/.ssh/id_ed25519_onigiri
```

SSH가 이 키를 사용할 수 있도록 `~/.ssh/config`를 설정하는 것이 편합니다.

```bash
nano ~/.ssh/config   # vi, vim 등 아무 에디터 사용 가능
```

안에 아래 내용 추가:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_onigiri
    IdentitiesOnly yes
```

의미는 다음과 같습니다.

* `Host github-myrepo` : 이 이름으로 SSH 접속할 때 아래 설정을 사용.
* `HostName github.com` : 실제 접속할 호스트는 github.com.
* `User git` : GitHub SSH 접속 계정은 항상 `git`.
* `IdentityFile` : 방금 만든 비밀키 경로.
* `IdentitiesOnly yes` : 이 키만 사용하게 강제.

`~/.ssh/config` 파일 권한도 맞춰 줍니다.

```bash
chmod 600 ~/.ssh/config
```

---

## 4. SSH 접속 테스트

Deploy key가 제대로 등록되었는지 테스트합니다.

```bash
ssh -T github.com
```

처음 접속이면 다음과 같은 host key 확인 메시지가 뜹니다.

```text
The authenticity of host 'github.com (IP ...)' can't be established.
...
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

→ `yes` 입력 후 엔터.

정상이라면 대략 이런 메시지가 나옵니다.

```text
Hi <owner>/<repo-name>! You've successfully authenticated, but GitHub does not provide shell access.
```

* 여기서 `<owner>/<repo-name>`이 해당 Private 리포 이름이면 성공입니다.
* 에러가 난다면:

  * Deploy key를 “해당 리포지토리”에 제대로 붙였는지
  * `config`에 `IdentityFile` 경로가 정확한지
  * 서버와 GitHub 간 네트워크가 열려 있는지
    를 다시 확인하시면 됩니다.

---

## 5. 리포지토리 clone 또는 기존 리포 Remote 설정

### 5-1. 새로 clone 하는 경우

SSH URL 형태:

```bash
git clone git@github.com:<owner>/<repo>.git
```

예를 들어 `owner`가 `identicalparticle`, 리포가 `my-private-repo`라면:

```bash
git clone git@github.com:identicalparticle/my-private-repo.git
```

위에서 `Host github-myrepo`를 설정했지만, 실제 git URL은 `git@github.com:...` 그대로 사용해도 됩니다.
SSH는 hostname이 `github.com`일 때 `~/.ssh/config`의 `HostName` 매칭 규칙에 따라 키를 찾아 사용합니다.
(만약 여러 개의 다른 키를 쓰는 복잡한 상황에서는 `git@github-myrepo:owner/repo.git`처럼 Host alias를 직접 쓸 수도 있습니다.)

clone이 끝나면 디렉터리로 이동하여 `git pull`을 테스트해 봅니다.

```bash
cd my-private-repo
git pull
```

아무 변경사항이 없다면 “Already up to date.” 정도가 뜨면 정상입니다.

---

### 5-2. 이미 HTTPS 또는 다른 SSH 키로 clone된 리포가 있을 경우

이미 받아놓은 리포의 remote URL을 교체할 수도 있습니다.

```bash
cd /path/to/your/existing/repo

# 현재 remote 확인
git remote -v

# origin을 SSH URL로 변경
git remote set-url origin git@github.com:<owner>/<repo>.git

# 테스트
git pull
```

---

## 6. 운영 시 유의사항

마지막으로 몇 가지 운영 팁을 정리하겠습니다.

1. **리포지토리마다 키 분리 권장**

   * Deploy key는 한 개의 리포지토리에만 직접 붙일 수 있습니다.
   * 같은 공개키를 여러 리포에 재사용하는 것도 가능하지만, 보안 관점에서는 리포당 1키가 더 명확합니다.

2. **서버 계정 권한 관리**

   * 이 Deploy key가 저장된 서버 계정에 접근할 수 있는 사람 = 이 Private 리포에 read 권한을 가진 사람입니다.
   * 서버 계정 접근 권한 관리에 신경 쓰셔야 합니다.

3. **write 권한 부여 시 주의**

   * `Allow write access`를 켜면 그 서버에서 `git push`도 가능합니다.
   * 자동 배포 서버라면 보통 read-only로 충분한 경우가 많으니, 정말 필요할 때만 write로 두는 것이 안전합니다.

4. **CI/CD 시스템에서 사용 시**

   * GitLab Runner, Jenkins, cron job 등에서도 기본 구조는 동일합니다.
   * 해당 러너/유저 계정의 `~/.ssh`에 키를 넣고, 같은 방식으로 `config`를 설정한 다음 `git pull` 스크립트를 실행하면 됩니다.

---

요약하면,

1. 서버에서 `ssh-keygen`으로 전용 키 생성
2. 공개키를 GitHub 리포의 Deploy key에 추가
3. 서버 `~/.ssh/config`에 키를 등록
4. `ssh -T`로 테스트 후
5. `git clone` 또는 `git remote set-url` → `git pull` 확인

이 순서로 진행하시면 됩니다.

중간에 특정 에러 메시지가 뜨면, 그 메시지 그대로 알려 주시면 거기서부터 디버깅을 같이 정리해 드리겠습니다.
