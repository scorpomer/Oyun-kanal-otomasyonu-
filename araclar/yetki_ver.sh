#!/data/data/com.termux/files/usr/bin/bash
# Termux: bir GitHub hesabinin tum depolarina baska bir hesaba yazma yetkisi verir
# ve (istege bagli) o hesapla davetleri kabul eder.
set -uo pipefail
HEDEF="${1:-scorpomer}"

echo "[1/3] GitHub CLI kuruluyor..."
pkg install -y gh >/dev/null 2>&1 || { echo "gh kurulamadi"; exit 1; }

echo ""
echo "[2/3] Depolari PAYLASACAK hesapla giris yapin (or: Yagmur Yalcin)."
echo "      Ekrana cikan 8 haneli kodu kopyalayin, acilan sayfada o hesapla girip kodu yapistirin."
gh auth login -h github.com -p https -w || exit 1
SAHIP=$(gh api user --jq .login) || exit 1

mapfile -t DEPOLAR < <(gh repo list "$SAHIP" --limit 300 --json name --jq '.[].name')
echo ""
echo "Giris yapilan hesap: $SAHIP  (${#DEPOLAR[@]} depo)"
printf '  - %s\n' "${DEPOLAR[@]}"
read -rp "Bu depolarin HEPSINE '$HEDEF' hesabina yazma yetkisi verilsin mi? (e/H): " c
[ "${c,,}" = "e" ] || { echo "Iptal edildi."; exit 0; }

for r in "${DEPOLAR[@]}"; do
    if gh api -X PUT "repos/$SAHIP/$r/collaborators/$HEDEF" -f permission=push >/dev/null 2>&1; then
        echo "  + $r"
    else
        echo "  ! $r (eklenemedi)"
    fi
done

echo ""
echo "[3/3] Davetleri kabul etmek icin '$HEDEF' hesabiyla giris"
read -rp "Simdi '$HEDEF' ile girip davetleri otomatik kabul edelim mi? (E/h): " c2
if [ "${c2,,}" != "h" ]; then
    gh auth login -h github.com -p https -w || exit 1
    if [ "$(gh api user --jq .login)" != "$HEDEF" ]; then
        echo "'$HEDEF' ile giris yapilmadi; davetleri github.com/notifications adresinden elle kabul edin."
        exit 1
    fi
    n=0
    while read -r id; do
        [ -n "$id" ] || continue
        gh api -X PATCH "user/repository_invitations/$id" >/dev/null 2>&1 && n=$((n + 1))
    done < <(gh api user/repository_invitations --paginate --jq ".[] | select(.repository.owner.login==\"$SAHIP\") | .id")
    echo "  $n davet kabul edildi."
fi

echo ""
echo "TAMAM. Claude'a 'yetki verildi' yazabilirsiniz."
