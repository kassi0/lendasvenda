const CONFIG = {
    initialBid: 300,
    bidIncrement: 20
};

let currentMinBid = CONFIG.initialBid;

document.addEventListener("DOMContentLoaded", () => {
    // 1. Identificar domínio do host atual
    const domainHeading = document.getElementById("domainName");
    const hostname = window.location.hostname;

    if (hostname && hostname !== "localhost" && hostname !== "127.0.0.1") {
        domainHeading.textContent = hostname;
        document.title = `${hostname} - Transferência de Domínio`;
    }

    const domain = domainHeading.textContent.trim();

    // 2. Ano dinâmico
    const yearSpan = document.getElementById("year");
    if (yearSpan) {
        yearSpan.textContent = new Date().getFullYear();
    }

    // 3. Carregar dados atuais do leilão
    loadAuctionStats();

    // 4. Submissão do Lance
    const bidForm = document.getElementById("bidForm");
    const bidAlert = document.getElementById("bidAlert");
    const bidSubmitBtn = document.getElementById("bidSubmitBtn");

    bidForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const name = document.getElementById("bidName").value.trim();
        const email = document.getElementById("bidEmail").value.trim();
        const whatsapp = document.getElementById("bidWhatsapp").value.trim();
        const amount = parseFloat(document.getElementById("bidAmount").value);

        if (isNaN(amount) || amount < currentMinBid) {
            showAlert(`O valor mínimo para novo lance é de R$ ${formatBRL(currentMinBid)}.`, "error");
            return;
        }

        bidSubmitBtn.disabled = true;
        bidSubmitBtn.textContent = "Processando lance...";
        hideAlert();

        try {
            const response = await fetch("/api/bids", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    domain: domain,
                    name: name,
                    email: email,
                    whatsapp: whatsapp,
                    amount: amount
                })
            });

            const result = await response.json();

            if (response.ok && result.success) {
                showAlert(`Lance de R$ ${formatBRL(amount)} registrado com sucesso. Você será notificado por e-mail ou WhatsApp.`, "success");
                bidForm.reset();
                loadAuctionStats();
            } else {
                showAlert(result.error || "Não foi possível registrar a proposta.", "error");
            }
        } catch (error) {
            showAlert("Falha na comunicação com o servidor de lances.", "error");
        } finally {
            bidSubmitBtn.disabled = false;
            bidSubmitBtn.textContent = "Registrar Lance";
        }
    });

    function showAlert(text, type) {
        bidAlert.className = `notification ${type}`;
        bidAlert.textContent = text;
    }

    function hideAlert() {
        bidAlert.className = "notification";
        bidAlert.textContent = "";
    }

    async function loadAuctionStats() {
        try {
            const res = await fetch("/api/bids/stats");
            if (!res.ok) return;

            const stats = await res.json();

            const initialDisplay = document.getElementById("initialBidDisplay");
            const highestDisplay = document.getElementById("currentHighestDisplay");
            const minNotice = document.getElementById("minBidNotice");
            const bidInput = document.getElementById("bidAmount");

            initialDisplay.textContent = `R$ ${formatBRL(stats.initialBid)}`;
            highestDisplay.textContent = `R$ ${formatBRL(stats.currentHighest)}`;

            currentMinBid = stats.minNextBid;
            bidInput.min = currentMinBid;
            bidInput.placeholder = currentMinBid;
            minNotice.textContent = `Mínimo aceito para próximo lance: R$ ${formatBRL(currentMinBid)}`;

            // Exibir lista com nomes ofuscados
            const historyCard = document.getElementById("historyCard");
            const recentBidsBody = document.getElementById("recentBidsBody");

            if (stats.recentBids && stats.recentBids.length > 0) {
                historyCard.style.display = "block";
                recentBidsBody.innerHTML = stats.recentBids.map(b => `
                    <tr>
                        <td class="bidder">${escapeHtml(b.bidder)}</td>
                        <td class="amount">R$ ${formatBRL(b.amount)}</td>
                    </tr>
                `).join('');
            } else {
                historyCard.style.display = "none";
            }
        } catch (err) {
            currentMinBid = CONFIG.initialBid;
        }
    }

    function formatBRL(val) {
        return Number(val || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function escapeHtml(str) {
        return String(str || '').replace(/[&<>"']/g, function(m) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m];
        });
    }
});
