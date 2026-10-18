/* =========================================================
   İETT VERİ ANALİZ SİSTEMİ
   ORTAK PANEL JAVASCRIPT
   ========================================================= */


/* =========================================================
   TARİH VE SAAT
   ========================================================= */

function updateDateTime() {

    const now = new Date();

    const dateElement = document.getElementById("currentDate");
    const timeElement = document.getElementById("currentTime");


    if (dateElement) {

        const date = now.toLocaleDateString("tr-TR", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric"
        });

        dateElement.textContent = date;

    }


    if (timeElement) {

        const time = now.toLocaleTimeString("tr-TR", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });

        timeElement.textContent = time;

    }

}


/* Sayfa açıldığında çalıştır */

updateDateTime();


/* Her saniye güncelle */

setInterval(updateDateTime, 1000);


/* =========================================================
   MOBİL SIDEBAR
   ========================================================= */

const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const sidebar = document.getElementById("sidebar");


if (mobileMenuBtn && sidebar) {

    mobileMenuBtn.addEventListener("click", function () {

        sidebar.classList.toggle("open");

    });

}


/* =========================================================
   MOBİLDE SIDEBAR DIŞINA TIKLAYINCA KAPAT
   ========================================================= */

document.addEventListener("click", function (event) {

    if (!sidebar || !mobileMenuBtn) {
        return;
    }


    const clickedInsideSidebar = sidebar.contains(event.target);
    const clickedMenuButton = mobileMenuBtn.contains(event.target);


    if (
        window.innerWidth <= 850 &&
        !clickedInsideSidebar &&
        !clickedMenuButton
    ) {

        sidebar.classList.remove("open");

    }

});


/* =========================================================
   EKRAN GENİŞLİĞİ DEĞİŞİNCE SIDEBAR KONTROLÜ
   ========================================================= */

window.addEventListener("resize", function () {

    if (!sidebar) {
        return;
    }


    if (window.innerWidth > 850) {

        sidebar.classList.remove("open");

    }

});