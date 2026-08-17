# Informe — El superusuario sin restricciones + decisiones de producto de David

**Fecha:** 2026-08-17 · **Operador:** Claude Code · **Commit:** `c765516`
**Origen:** órdenes de David tras leer el informe del pase 4.3-A.8 (`docs/30`)

---

## 1. Lo que has decidido y qué he hecho con cada cosa

| Tu decisión | Qué es | Estado |
|---|---|---|
| «La cuenta superusuario no debe tener restricciones» | Cambio de código | ✅ **Hecho y desplegado** |
| «Dinero real, está ok» | Confirmación | ✅ Nada que hacer; documentado |
| «Exigir dinero a quien analice un vídeo de más de 40 frases/min» | Decisión de producto | 📨 **Pasada a Fable con un escollo** (§4) |
| «Notificación + email a quienes votaron; el gasto entra en el diario/mensual» | Decisión de producto | 📨 **Pasada a Fable** — confirma la B4 |

---

## 2. El superusuario ya no tiene restricciones de edad

**El problema**: `ensure_superuser` no establece fecha de nacimiento, y todo el candado +18
se apoya en `User.is_adult`, que la exige. Resultado: el dueño de la plataforma se quedaba
fuera de su propia sala con un 403.

**El arreglo**, en `apps/accounts/models.py`:

```python
@property
def is_adult(self):
    if self.is_superuser:
        return True
    return self.age is not None and self.age >= 18
```

Un solo punto arregla toda la web, porque el menú «+18», la vista `/mas18/`, los filtros de
portada y la pantalla de ajustes cuelgan **todos** de esa misma propiedad. No hay que tocar
cuatro sitios ni arriesgarse a que uno se quede descoordinado.

**Lo que NO he hecho, a propósito**: el privilegio es **solo del superusuario**. El staff y
los moderadores siguen sujetos a su fecha de nacimiento. Dijiste «la cuenta superusuario», y
regalar la mayoría de edad a cualquiera con acceso al panel sería una decisión distinta que
no me has pedido. Hay un test que fija ambas mitades de la regla: el superusuario sin fecha
entra (200 y ve el menú), un usuario solo-staff sin fecha no (403).

> **Para ti, en la práctica**: entra en escierto.xyztserver.com con tu cuenta `d` y verás el
> enlace **+18** en el menú. Ya no necesitas ponerte fecha de nacimiento.

---

## 3. Confirmada la decisión B4: aviso, no muro

Tu respuesta cierra la pregunta que Fable tenía abierta:

> «a las personas que hayan votado por analizar un vídeo tan largo, se les emitirá una
> notificación e email de las consecuencias económicas, sin más. El gasto entrará en el
> gasto diario/mensual».

Queda anotado en `docs/06 §29.2` con tres condiciones para Fable: el aviso va **a quienes
votaron** (no solo a quien lo envió), respeta el circuito de preferencias que ya existe
(campana, silencio nocturno, digest), y el gasto pasa por `try_spend` como cualquier otro —
sin vías de gasto paralelas.

Eso es funcionalidad nueva y es trabajo de Fable, no lo he construido yo. Si prefieres que
lo implemente directamente (como hice con el autocompletado de Wikidata), dímelo.

---

## 4. Cobrar por densidad: la idea es buena, pero hay un escollo

Tu razonamiento es correcto y los números lo respaldan: un vídeo denso (44,1 frases/min)
genera **casi el triple de lotes** que uno tranquilo (16,1 frases/min) con la misma
duración, y hoy los dos pagan igual porque el precio solo mira los minutos.

**El escollo**: las frases por minuto **no se saben hasta haber transcrito el vídeo**, y la
transcripción es justo una de las partes caras. Es como cobrar la cuenta del restaurante
según lo que pese el cliente al salir: el dato solo existe cuando ya te has gastado la
comida. Cobrar por adelantado en función de la densidad, tal cual está enunciado, no se
puede hacer.

He pasado a Fable tres salidas posibles (`docs/06 §29.3`) para que elija y tú confirmes:

1. **Dos tramos** — se sugiere por minutos al empezar y, si al terminar la transcripción la
   densidad se dispara, se avisa del sobrecoste y se pide un complemento voluntario. Es lo
   más coherente con tu «aviso, no muro».
2. **Estimación previa por señales baratas** — plataforma, si es un debate o tertulia,
   duración, histórico del canal. Acertará a veces; es una apuesta.
3. **Reserva por el peor caso** — cobrar suponiendo densidad alta y devolver la diferencia.
   Lo más justo, lo más incómodo de explicar al usuario.

Mi recomendación es la **1**: encaja con la decisión que acabas de tomar en el punto 3 y no
exige adivinar nada.

---

## 5. Verificación y estado

| | |
|---|---|
| **CI** | Verde, **101/101** — [run 31983028258](https://github.com/nulltimed/isthistrue/actions/runs/31983028258) |
| **Espejo** | 101/101 tests · tu cuenta `d` (sin fecha de nacimiento) entra con **200** y ve el menú · APAGADO |
| **Producción** | `c765516`, 6 contenedores Up, 0 errores en logs |
| **Producción — sala +18 con tu cuenta** | **HTTP 200** y enlace +18 visible en el menú |
| **Producción — sin sesión** | **HTTP 403** (el candado sigue cerrado para el público) |
| **Estáticos** | `CSS 200 · 27.966 bytes · masthead 1` en los tres dominios |
| **Copia previa** | `/opt/isthistrue.bak-20260817-0251` |
| **Migraciones** | Ninguna (el cambio es una propiedad calculada, no un campo) |
| **Documentos** | `docs/06 §29` (canal a Fable), handoff §10, este informe |
