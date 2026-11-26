/*
 * Portadas desde Open Library (https://openlibrary.org)
 *
 * Para cada libro SIN portada subida (elementos .portada con data-isbn):
 *   1. Intenta la portada por ISBN:  covers.openlibrary.org/b/isbn/{ISBN}-M.jpg
 *   2. Si no hay, busca por título y autor en openlibrary.org/search.json
 *      y usa la portada de la primera coincidencia (cover_i).
 *   3. Si tampoco hay, se queda el lomo de tela que ya pinta la plantilla.
 *
 * Es solo una mejora visual: si Open Library no responde o no hay internet,
 * la página funciona igual. Los resultados se guardan en localStorage
 * para no repetir las consultas en cada visita.
 */
(function () {
    "use strict";

    var PORTADAS = "https://covers.openlibrary.org/b/";
    var BUSQUEDA = "https://openlibrary.org/search.json";
    var SIN_PORTADA = "-";
    var DIAS_CACHE = 14;
    var SIMULTANEAS = 3;              // no saturar a Open Library

    // ---- caché en localStorage (puede no existir o estar llena) ----------
    function leerCache(clave) {
        try {
            var dato = JSON.parse(localStorage.getItem("portada:" + clave));
            if (dato && Date.now() - dato.t < DIAS_CACHE * 864e5) return dato.url;
        } catch (e) { /* sin caché */ }
        return null;
    }

    function guardarCache(clave, url) {
        try {
            localStorage.setItem("portada:" + clave, JSON.stringify({ url: url, t: Date.now() }));
        } catch (e) { /* sin caché */ }
    }

    // ---- utilidades -------------------------------------------------------
    // Resuelve con la URL si la imagen existe (Open Library responde 404
    // gracias a ?default=false cuando no tiene portada).
    function probarImagen(url) {
        return new Promise(function (resolver) {
            var img = new Image();
            img.onload = function () { resolver(img.naturalWidth > 1 ? url : null); };
            img.onerror = function () { resolver(null); };
            img.src = url;
        });
    }

    function buscarPorTitulo(titulo, autor) {
        var params = new URLSearchParams({ title: titulo, limit: "1", fields: "cover_i" });
        if (autor) params.set("author", autor);
        return fetch(BUSQUEDA + "?" + params.toString())
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (datos) {
                var doc = datos && datos.docs && datos.docs[0];
                return doc && doc.cover_i ? PORTADAS + "id/" + doc.cover_i + "-M.jpg" : null;
            })
            .catch(function () { return null; });
    }

    function encontrarPortada(el) {
        var isbn = (el.dataset.isbn || "").replace(/[^0-9Xx]/g, "");
        var clave = isbn || el.dataset.titulo;
        var guardada = leerCache(clave);
        if (guardada) return Promise.resolve(guardada === SIN_PORTADA ? null : guardada);

        var porIsbn = isbn
            ? probarImagen(PORTADAS + "isbn/" + isbn + "-M.jpg?default=false")
            : Promise.resolve(null);

        return porIsbn
            .then(function (url) {
                return url || buscarPorTitulo(el.dataset.titulo, el.dataset.autor);
            })
            .then(function (url) {
                guardarCache(clave, url || SIN_PORTADA);
                return url;
            });
    }

    function ponerImagen(el, url) {
        var img = document.createElement("img");
        img.alt = "";                        // el título ya está escrito junto a la portada
        img.setAttribute("data-cargando", "");
        img.onload = function () {
            img.removeAttribute("data-cargando");
            img.classList.add("lista");
        };
        img.onerror = function () { img.remove(); };
        img.src = url;
        el.appendChild(img);
    }

    // ---- cola con pocas consultas a la vez ----------------------------------
    var cola = [];
    var activas = 0;

    function siguiente() {
        while (activas < SIMULTANEAS && cola.length) {
            var el = cola.shift();
            activas++;
            encontrarPortada(el)
                .then(function (url) { if (url) ponerImagen(this, url); }.bind(el))
                .finally(function () { activas--; siguiente(); });
        }
    }

    function encolar(el) {
        cola.push(el);
        siguiente();
    }

    // ---- inicio: solo las portadas que están por verse ----------------------
    var portadas = document.querySelectorAll(".portada[data-isbn]");
    if (!portadas.length || !window.fetch || !window.Promise) return;

    if ("IntersectionObserver" in window) {
        var observador = new IntersectionObserver(function (entradas) {
            entradas.forEach(function (entrada) {
                if (entrada.isIntersecting) {
                    observador.unobserve(entrada.target);
                    encolar(entrada.target);
                }
            });
        }, { rootMargin: "300px 0px" });
        portadas.forEach(function (el) { observador.observe(el); });
    } else {
        portadas.forEach(encolar);
    }
})();