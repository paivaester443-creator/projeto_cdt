const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");


function atualizarTema() {

    const modoEscuro =
        document.documentElement.classList.contains("dark");

    if (themeIcon) {

        themeIcon.textContent =
            modoEscuro
                ? "Modo claro"
                : "Modo escuro";
    }
}


const temaSalvo =
    localStorage.getItem("sintonia-theme");


if (
    temaSalvo === "dark" ||
    (
        !temaSalvo &&
        window.matchMedia(
            "(prefers-color-scheme: dark)"
        ).matches
    )
) {

    document.documentElement.classList.add(
        "dark"
    );
}


atualizarTema();


if (themeToggle) {

    themeToggle.addEventListener(
        "click",
        function () {

            document.documentElement.classList.toggle(
                "dark"
            );

            const modoEscuro =
                document.documentElement.classList.contains(
                    "dark"
                );

            localStorage.setItem(
                "sintonia-theme",
                modoEscuro
                    ? "dark"
                    : "light"
            );

            atualizarTema();
        }
    );
}


/* =====================================================
   LOCALIZAÇÃO
===================================================== */

const cidadeInput =
    document.getElementById("cidade");

const latitudeInput =
    document.getElementById("latitude");

const longitudeInput =
    document.getElementById("longitude");

const locationButton =
    document.getElementById("locationButton");

const locationStatus =
    document.getElementById("locationStatus");


function limparCoordenadas() {

    if (latitudeInput) {
        latitudeInput.value = "";
    }

    if (longitudeInput) {
        longitudeInput.value = "";
    }
}


/*
Quando a pessoa começa a digitar outra cidade,
as coordenadas automáticas anteriores são removidas.

Isso é importante porque, por exemplo:

Localização automática:
Seul

Depois o usuário digita:
São Paulo

O sistema precisa consultar São Paulo,
e não continuar usando as coordenadas de Seul.
*/

if (cidadeInput) {

    cidadeInput.addEventListener(
        "input",
        function () {

            limparCoordenadas();

            if (locationStatus) {

                locationStatus.textContent =
                    "Cidade escolhida manualmente.";
            }
        }
    );
}


async function buscarNomeCidade(
    latitude,
    longitude
) {

    try {

        const resposta = await fetch(
            "https://nominatim.openstreetmap.org/reverse" +
            `?format=jsonv2` +
            `&lat=${latitude}` +
            `&lon=${longitude}` +
            `&accept-language=pt-BR`
        );

        if (!resposta.ok) {
            throw new Error(
                "Falha na localização."
            );
        }

        const dados =
            await resposta.json();

        const endereco =
            dados.address || {};

        const cidade =
            endereco.city ||
            endereco.town ||
            endereco.municipality ||
            endereco.village ||
            endereco.county ||
            "";

        return cidade;

    } catch (erro) {

        return "";
    }
}


function obterLocalizacao() {

    if (!navigator.geolocation) {

        if (locationStatus) {

            locationStatus.textContent =
                "Seu navegador não oferece localização automática. Digite a cidade manualmente.";
        }

        return;
    }


    if (locationStatus) {

        locationStatus.textContent =
            "Obtendo sua localização...";
    }


    if (locationButton) {

        locationButton.disabled = true;
    }


    navigator.geolocation.getCurrentPosition(

        async function (position) {

            const latitude =
                position.coords.latitude;

            const longitude =
                position.coords.longitude;


            if (latitudeInput) {
                latitudeInput.value =
                    latitude;
            }


            if (longitudeInput) {
                longitudeInput.value =
                    longitude;
            }


            const cidade =
                await buscarNomeCidade(
                    latitude,
                    longitude
                );


            if (cidadeInput && cidade) {

                cidadeInput.value =
                    cidade;
            }


            if (locationStatus) {

                if (cidade) {

                    locationStatus.textContent =
                        "Localização detectada: " +
                        cidade +
                        ".";

                } else {

                    locationStatus.textContent =
                        "Localização detectada. O clima será calculado pelas coordenadas.";
                }
            }


            if (locationButton) {

                locationButton.disabled = false;
            }
        },


        function () {

            limparCoordenadas();


            if (locationStatus) {

                locationStatus.textContent =
                    "Não foi possível obter sua localização. Você pode digitar a cidade manualmente.";
            }


            if (locationButton) {

                locationButton.disabled = false;
            }
        },


        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 300000
        }
    );
}


/*
Quando o dashboard abre,
tentamos obter a localização automaticamente.

O navegador vai pedir permissão.
Se a pessoa negar, nada quebra:
ela simplesmente poderá digitar a cidade.
*/

if (
    cidadeInput &&
    locationButton
) {

    obterLocalizacao();


    locationButton.addEventListener(
        "click",
        function () {

            obterLocalizacao();
        }
    );
}