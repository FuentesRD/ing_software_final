# Sistema de Gestión de Biblioteca Escolar

Proyecto final de Ingeniería de Software · Agosto–Diciembre 2026

## Equipo
- Diego
- Alvaro
- Samanta
- Ricardo

## Stack
Python 3.12 · Django 5.2 · MySQL 8.4 (Docker) · Bootstrap 5 · Visual Paradigm

## Estructura del repositorio
```
CLAUDE.md        Instrucciones del proyecto para Claude Code
docs/            Requerimientos, diagramas UML (.vpp) y diseño de BD
  bd/            esquema_bd_biblioteca.html (referencia principal) y modelo ER original
docker/          Configuración de MySQL en Docker        (Fase 1)
biblioteca/      Configuración de Django                  (Fase 2)
cuentas/, catalogo/, prestamos/, multas/, ...  Apps        (Fase 3+)
```
## Plan de trabajo
El reparto de tareas, los contratos entre apps y el calendario están en
[`PLAN_DE_TRABAJO.md`](PLAN_DE_TRABAJO.md).

## Flujo de trabajo con Git
| Rama | Uso |
|---|---|
| `main` | Solo versiones entregadas (etiquetas `entrega-1`, `entrega-2`, ...) |
| `develop` | Integración del trabajo diario |
| `feature/<tarea>` | Una rama por tarea, sale de `develop` y regresa por Pull Request |

1. `git switch develop && git pull`
2. `git switch -c feature/mi-tarea`
3. Commits pequeños con prefijo: `feat:`, `fix:`, `docs:`, `test:`, `chore:`
4. `git push -u origin feature/mi-tarea` y abrir PR hacia `develop`
5. Otro integrante revisa y aprueba el PR

## Instalación
*(Se completa en la Fase 1 y 2)*
