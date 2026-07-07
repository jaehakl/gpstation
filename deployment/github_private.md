# GitHub private repository deploy key

Use a read-only deploy key for the production server.

## 1. Generate a key on the server

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -C "deploy-key-for-gpstation" -f ~/.ssh/id_ed25519_gpstation
chmod 600 ~/.ssh/id_ed25519_gpstation
```

Leave the passphrase empty for non-interactive `git pull`.

## 2. Register the public key in GitHub

In the GitHub repository:

1. Open `Settings > Deploy keys`.
2. Click `Add deploy key`.
3. Paste:

```bash
cat ~/.ssh/id_ed25519_gpstation.pub
```

4. Keep write access disabled unless the server must push.

## 3. Configure SSH

Add this to `~/.ssh/config`:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_gpstation
    IdentitiesOnly yes
```

```bash
chmod 600 ~/.ssh/config
ssh -T github.com
```

## 4. Clone or update the repo

```bash
git clone git@github.com:<owner>/<repo>.git /home/ubuntu/gpstation
cd /home/ubuntu/gpstation
git pull --ff-only
```
