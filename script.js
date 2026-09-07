/* =========================================================
   VOICE VAULT AI
   GLOBAL JAVASCRIPT
========================================================= */


/* =========================================================
   DARK MODE
========================================================= */

function toggleDarkMode() {

    document.body.classList.toggle("dark-mode");

    const darkModeButton =
        document.getElementById("darkModeBtn");


    /* DARK MODE ENABLED */

    if (document.body.classList.contains("dark-mode")) {

        localStorage.setItem(
            "darkMode",
            "enabled"
        );

        if (darkModeButton) {

            darkModeButton.innerHTML = "☀️";
            darkModeButton.title = "Switch to Light Mode";

        }

    }

    /* LIGHT MODE */

    else {

        localStorage.setItem(
            "darkMode",
            "disabled"
        );

        if (darkModeButton) {

            darkModeButton.innerHTML = "🌙";
            darkModeButton.title = "Switch to Dark Mode";

        }

    }

}


/* =========================================================
   LOAD DARK MODE
========================================================= */

function loadDarkMode() {

    const darkMode =
        localStorage.getItem("darkMode");

    const darkModeButton =
        document.getElementById("darkModeBtn");


    if (darkMode === "enabled") {

        document.body.classList.add("dark-mode");

        if (darkModeButton) {

            darkModeButton.innerHTML = "☀️";
            darkModeButton.title = "Switch to Light Mode";

        }

    }

}


/* =========================================================
   PAGE LOAD
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        loadDarkMode();

    }
);