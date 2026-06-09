"""Automatización del portal WhaleTV Lock Management con Selenium.

Flujo: login -> buscar el MAC -> abrir Detail -> (dry-run) leer el estado remoto
y compararlo con el estado local; en modo real, ajustar Lock/fecha y Save.

El portal es una SPA en Vue + Element-UI, así que se controla como un humano.
Los selectores se basan en texto/atributos estables (no en los data-v-* dinámicos).
"""

from dataclasses import dataclass, field

from django.conf import settings
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@dataclass
class ResultadoSync:
    ok: bool = False
    error: str = ''
    log: list = field(default_factory=list)
    remoto_bloqueado: bool | None = None
    remoto_next_date: str = ''
    local_bloqueado: bool | None = None
    cambiaria: bool | None = None
    aplicado: bool = False

    def paso(self, msg):
        self.log.append(msg)


def _build_driver(headless):
    import os

    from selenium.webdriver.chrome.service import Service

    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--window-size=1400,900')
    options.add_argument('--disable-blink-features=AutomationControlled')
    # Flags necesarios en contenedores (Docker/Render): sin sandbox ni /dev/shm.
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])

    # En servidor/Docker se define el binario de Chromium y el driver por env.
    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver = os.environ.get('CHROMEDRIVER')
    if chromedriver:
        return webdriver.Chrome(service=Service(executable_path=chromedriver), options=options)

    # Local: Selenium Manager descarga el driver automáticamente.
    return webdriver.Chrome(options=options)


def _login(driver, wait, cfg, res):
    res.paso('Abriendo login...')
    driver.get(cfg['LOGIN_URL'])

    email = wait.until(EC.presence_of_element_located((By.NAME, 'account')))
    password = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    email.clear()
    email.send_keys(cfg['EMAIL'])
    password.clear()
    password.send_keys(cfg['PASSWORD'])
    res.paso(f"Credenciales ingresadas ({cfg['EMAIL']}).")

    # Botón Login (span con texto "Login").
    boton = driver.find_element(
        By.XPATH, "//button[.//span[normalize-space(text())='Login']]"
    )
    boton.click()
    res.paso('Click en Login, esperando lista de dispositivos...')

    # Esperamos a que cargue la lista de dispositivos.
    wait.until(EC.url_contains('deviceManage'))
    res.paso('Sesión iniciada.')


def _macs_visibles(driver):
    """Devuelve la lista de MACs visibles (en orden de fila).

    La columna MAC visible está en la tabla fija de la izquierda; si no hay
    columnas fijas, cae a la tabla principal.
    """
    selectores = [
        '.el-table__fixed .el-table__fixed-body-wrapper .el-table__row',
        '.el-table__body-wrapper .el-table__row',
    ]
    for sel in selectores:
        filas = driver.find_elements(By.CSS_SELECTOR, sel)
        macs = [f.text.strip().upper() for f in filas]
        if any(m for m in macs):
            return macs
    return []


def _abrir_detalle_en_indice(driver, wait, indice, mac, res):
    """Hace click en el link Detail de la fila `indice` y espera que carguen datos."""
    detalles = driver.find_elements(
        By.XPATH,
        "//div[contains(@class,'el-table__fixed-right')]"
        "//a[contains(@class,'toDetail')]",
    )
    if not detalles:
        detalles = driver.find_elements(
            By.XPATH, "//a[contains(@class,'toDetail')]"
        )

    if indice >= len(detalles):
        raise RuntimeError('No encontré el link Detail de la fila localizada.')

    link = detalles[indice]
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
    try:
        link.click()
    except Exception:  # noqa: BLE001
        driver.execute_script("arguments[0].click();", link)

    wait.until(EC.presence_of_element_located(
        (By.XPATH, "//strong[normalize-space(text())='Device Info']")
    ))
    res.paso(f'Detail abierto. URL: {driver.current_url}')

    # Esperamos a que la tabla Device Info muestre el MAC (datos reales cargados).
    mac_norm = mac.strip().upper()
    try:
        WebDriverWait(driver, 12).until(
            lambda d: mac_norm in (
                d.find_element(By.CSS_SELECTOR, '.device-info').text.upper()
            )
        )
        res.paso('Datos del dispositivo cargados en Detail.')
        return True
    except Exception:  # noqa: BLE001
        cuerpo = ''
        try:
            cuerpo = driver.find_element(By.CSS_SELECTOR, '.device-info').text.strip()
        except Exception:  # noqa: BLE001
            pass
        res.paso(f'Detail SIN datos (Device Info="{cuerpo[:60]}"). El click no llevó el dispositivo.')
        return False


def _abrir_detalle_por_mac(driver, wait, cfg, mac, res, max_paginas=20):
    """Busca el MAC recorriendo páginas y abre su Detail. True si lo logró."""
    if 'deviceList' not in driver.current_url:
        driver.get(cfg['DEVICE_LIST_URL'])

    wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, '.el-table__row')
    ))

    mac_norm = mac.strip().upper()

    for pagina in range(1, max_paginas + 1):
        macs = _macs_visibles(driver)
        res.paso(f'Página {pagina}: {len(macs)} dispositivos.')

        for i, m in enumerate(macs):
            if mac_norm in m:
                res.paso(f'MAC {mac} encontrado (página {pagina}, fila {i + 1}).')
                return _abrir_detalle_en_indice(driver, wait, i, mac, res)

        # Intentar pasar a la página siguiente.
        try:
            siguiente = driver.find_element(By.CSS_SELECTOR, '.el-pagination .btn-next')
            if siguiente.get_attribute('disabled'):
                break
            driver.execute_script("arguments[0].click();", siguiente)
            wait.until(EC.staleness_of(
                driver.find_element(By.CSS_SELECTOR, '.el-table__row')
            ))
        except Exception:  # noqa: BLE001
            break

    res.paso(f'MAC {mac} NO encontrado en el portal (revisé hasta {pagina} páginas).')
    return False


def _leer_estado_remoto(driver, res, diagnostico=False):
    """Lee del Detail si está bloqueado y la Next Installment Date.

    Si diagnostico=True, vuelca el HTML de la celda de Lock Status y guarda un
    screenshot para calibrar los selectores.
    """
    bloqueado = None

    # El estado se lee del icono: #icon-lock = bloqueado (div .lock),
    # #icon-unlock = desbloqueado (div .unlockChange). Leemos el primer <use>
    # con 'lock'/'unlock' dentro de la tabla de Lock Status.
    try:
        uses = driver.find_elements(By.CSS_SELECTOR, '.save-mode use')
        href = ''
        for u in uses:
            h = (u.get_attribute('xlink:href') or u.get_attribute('href') or '').lower()
            if 'unlock' in h:
                bloqueado = False
                href = h
                break
            if 'lock' in h:
                bloqueado = True
                href = h
                break
        res.paso(f'Icono lock remoto: {href or "(no encontrado)"} -> bloqueado={bloqueado}')
    except Exception as e:  # noqa: BLE001
        res.paso(f'No pude leer el icono de lock: {e}')

    if diagnostico:
        try:
            driver.save_screenshot('portal_detail.png')
            res.paso('Screenshot del Detail guardado en portal_detail.png')
        except Exception:  # noqa: BLE001
            pass

    res.remoto_bloqueado = bloqueado
    res.remoto_next_date = ''
    return bloqueado


def _set_lock_select(driver, wait, deseado, res):
    """Abre el select de Lock Status y elige 'Lock' o 'Unlock'."""
    selects = driver.find_elements(By.CSS_SELECTOR, '.el-select')
    if not selects:
        raise RuntimeError('No encontré el select de Lock Status en modo Edit.')

    lock_select = selects[0]  # el primero es Lock Status.
    actual = lock_select.find_element(By.CSS_SELECTOR, 'input').get_attribute('value')
    res.paso(f'Lock Status actual en portal: "{actual}", deseado: "{deseado}".')

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", lock_select)
    lock_select.click()

    xpath_item = (
        "//div[contains(@class,'el-select-dropdown') and not(contains(@style,'display: none'))]"
        f"//*[contains(@class,'el-select-dropdown__item')][normalize-space(.)='{deseado}']"
    )
    opcion = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, xpath_item))
    )
    opcion.click()

    nuevo = lock_select.find_element(By.CSS_SELECTOR, 'input').get_attribute('value')
    res.paso(f'Lock Status quedó en: "{nuevo}".')
    if nuevo != deseado:
        raise RuntimeError(f'No pude fijar Lock Status en "{deseado}" (quedó "{nuevo}").')


def _set_next_date(driver, fecha, res):
    """Escribe la Next Installment Date (formato MM/DD/YYYY)."""
    fecha_str = fecha.strftime('%m/%d/%Y')
    try:
        inp = driver.find_element(By.CSS_SELECTOR, '.el-date-editor input')
    except Exception:  # noqa: BLE001
        res.paso('No encontré el campo de fecha; lo omito.')
        return
    inp.click()
    inp.send_keys(Keys.CONTROL, 'a')
    inp.send_keys(fecha_str)
    inp.send_keys(Keys.ENTER)
    inp.send_keys(Keys.ESCAPE)
    res.paso(f'Next Installment Date escrita: {fecha_str}.')


def _aplicar_estado_remoto(driver, wait, televisor, res, sincronizar_fecha=True):
    """Edit -> ajustar Lock (y fecha) -> Save."""
    edit = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[.//span[normalize-space(text())='Edit']]")
    ))
    edit.click()
    res.paso('Click en Edit.')

    wait.until(EC.presence_of_element_located(
        (By.XPATH, "//button[.//span[normalize-space(text())='Save']]")
    ))

    deseado = 'Lock' if televisor.lock_status else 'Unlock'
    _set_lock_select(driver, wait, deseado, res)

    if sincronizar_fecha and televisor.fecha_sincronizar:
        _set_next_date(driver, televisor.fecha_sincronizar, res)

    save = driver.find_element(
        By.XPATH, "//button[.//span[normalize-space(text())='Save']]"
    )
    driver.execute_script("arguments[0].click();", save)
    res.paso('Click en Save.')

    # Confirmación: el botón Edit reaparece (volvió a modo lectura).
    WebDriverWait(driver, 15).until(EC.presence_of_element_located(
        (By.XPATH, "//button[.//span[normalize-space(text())='Edit']]")
    ))
    res.paso('Cambios guardados (volvió a modo lectura).')
    res.aplicado = True


def _procesar_televisor(driver, wait, cfg, televisor, res, dry_run, sincronizar_fecha):
    """Con sesión ya iniciada: busca el MAC, lee, compara y aplica.

    Mutates `res`. Asume que ya se hizo login en `driver`.
    """
    res.local_bloqueado = bool(televisor.lock_status)

    encontrado = _abrir_detalle_por_mac(driver, wait, cfg, televisor.mac_address, res)
    if not encontrado:
        res.ok = False
        res.error = f'No se encontró el MAC {televisor.mac_address} en el portal.'
        return res

    remoto = _leer_estado_remoto(driver, res, diagnostico=dry_run)

    if remoto is None:
        res.cambiaria = None
        res.paso('No se pudo determinar el estado remoto de bloqueo.')
    else:
        res.cambiaria = remoto != res.local_bloqueado
        estado_local = 'Bloqueado' if res.local_bloqueado else 'Desbloqueado'
        estado_remoto = 'Bloqueado' if remoto else 'Desbloqueado'
        res.paso(f'Local: {estado_local} | Remoto: {estado_remoto}')
        if res.cambiaria:
            res.paso('=> El estado remoto DEBERÍA cambiar para igualar al local.')
        else:
            res.paso('=> Ya están iguales, no hay nada que cambiar.')

    if dry_run:
        res.paso('DRY-RUN: no se modificó ni guardó nada en el portal.')
        res.aplicado = False
    else:
        if remoto is not None and not res.cambiaria and not (
            sincronizar_fecha and televisor.fecha_sincronizar
        ):
            res.paso('Estado ya coincide y no hay fecha que sincronizar: no toco nada.')
            res.aplicado = False
        else:
            _aplicar_estado_remoto(
                driver, wait, televisor, res, sincronizar_fecha=sincronizar_fecha
            )
            nuevo = _leer_estado_remoto(driver, res)
            res.remoto_bloqueado = nuevo
            res.cambiaria = (nuevo is not None and nuevo != res.local_bloqueado)

    res.ok = True
    return res


def sincronizar_televisor(televisor, dry_run=True, headless=None, sincronizar_fecha=True):
    """Sincroniza el estado del televisor con el portal de WhaleTV.

    En dry_run sólo lee el estado remoto y reporta qué cambiaría (no guarda).
    """
    cfg = settings.WHALETV_PORTAL
    if headless is None:
        headless = cfg.get('HEADLESS', False)

    res = ResultadoSync()
    res.local_bloqueado = bool(televisor.lock_status)

    driver = None
    try:
        driver = _build_driver(headless)
        wait = WebDriverWait(driver, cfg.get('TIMEOUT', 30))
        _login(driver, wait, cfg, res)
        _procesar_televisor(driver, wait, cfg, televisor, res, dry_run, sincronizar_fecha)
        return res
    except Exception as e:  # noqa: BLE001
        res.ok = False
        res.error = f'{type(e).__name__}: {e}'
        res.paso(f'ERROR: {res.error}')
        return res
    finally:
        if driver is not None:
            driver.quit()


def sincronizar_todos(televisores, dry_run=False, headless=None, sincronizar_fecha=True):
    """Sincroniza TODOS los televisores reusando una sola sesión (un login).

    Devuelve una lista de tuplas (televisor, ResultadoSync).
    """
    cfg = settings.WHALETV_PORTAL
    if headless is None:
        headless = cfg.get('HEADLESS', False)

    resultados = []
    driver = None
    try:
        driver = _build_driver(headless)
        wait = WebDriverWait(driver, cfg.get('TIMEOUT', 30))

        login_res = ResultadoSync()
        _login(driver, wait, cfg, login_res)

        for televisor in televisores:
            res = ResultadoSync()
            try:
                # Volvemos a la lista antes de cada TV.
                driver.get(cfg['DEVICE_LIST_URL'])
                _procesar_televisor(
                    driver, wait, cfg, televisor, res, dry_run, sincronizar_fecha
                )
            except Exception as e:  # noqa: BLE001
                res.ok = False
                res.error = f'{type(e).__name__}: {e}'
                res.paso(f'ERROR: {res.error}')
            resultados.append((televisor, res))

        return resultados

    except Exception as e:  # noqa: BLE001
        # Falló el login o el arranque: marcamos todos como error.
        for televisor in televisores:
            res = ResultadoSync()
            res.ok = False
            res.error = f'{type(e).__name__}: {e}'
            resultados.append((televisor, res))
        return resultados
    finally:
        if driver is not None:
            driver.quit()


# ---------------------------------------------------------------------------
# Sincronización masiva en segundo plano y en paralelo (para gran escala)
# ---------------------------------------------------------------------------

def ejecutar_job(job_id, workers=4, sincronizar_fecha=True):
    """Procesa un SyncJob en paralelo con varios navegadores (cada uno 1 login).

    Pensado para correr en un thread aparte (no bloquea la petición web).
    Cada worker toma televisores de una cola compartida y actualiza su item.
    """
    import queue
    import threading

    from django.db import connections
    from django.utils import timezone

    from .models import SyncJob, SyncJobItem, Televisor

    cfg = settings.WHALETV_PORTAL

    SyncJob.objects.filter(pk=job_id).update(estado='corriendo')

    pendientes = list(
        SyncJobItem.objects.filter(job_id=job_id, estado='pendiente')
        .values_list('pk', 'televisor_id')
    )
    cola = queue.Queue()
    for par in pendientes:
        cola.put(par)

    n_workers = max(1, min(int(workers), 8))

    def worker():
        driver = None
        try:
            driver = _build_driver(headless=True)
            wait = WebDriverWait(driver, cfg.get('TIMEOUT', 30))
            _login(driver, wait, cfg, ResultadoSync())

            while True:
                try:
                    item_pk, tv_id = cola.get_nowait()
                except queue.Empty:
                    break
                try:
                    tv = Televisor.objects.get(pk=tv_id)
                    res = ResultadoSync()
                    driver.get(cfg['DEVICE_LIST_URL'])
                    _procesar_televisor(
                        driver, wait, cfg, tv, res,
                        dry_run=False, sincronizar_fecha=sincronizar_fecha,
                    )
                    estado = 'ok' if res.ok else 'error'
                    mensaje = res.error if not res.ok else (
                        f'{"Bloqueado" if res.remoto_bloqueado else "Desbloqueado"}'
                        + (' · aplicado' if res.aplicado else ' · sin cambios')
                    )
                    SyncJobItem.objects.filter(pk=item_pk).update(
                        estado=estado, aplicado=res.aplicado, mensaje=mensaje[:500],
                    )
                except Exception as e:  # noqa: BLE001
                    SyncJobItem.objects.filter(pk=item_pk).update(
                        estado='error', mensaje=f'{type(e).__name__}: {e}'[:500],
                    )
                finally:
                    cola.task_done()
        except Exception as e:  # noqa: BLE001
            # Falló el arranque/login de este worker: deja sus items para otros.
            print(f'[sync worker] error: {e}')
        finally:
            if driver is not None:
                driver.quit()
            connections.close_all()

    hilos = [threading.Thread(target=worker, daemon=True) for _ in range(n_workers)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    # Cualquier item que quedó pendiente (p. ej. si todos los logins fallaron).
    SyncJobItem.objects.filter(job_id=job_id, estado='pendiente').update(
        estado='error', mensaje='No se procesó (revisa la conexión o credenciales).',
    )

    quedan_errores = SyncJobItem.objects.filter(job_id=job_id, estado='error').exists()
    SyncJob.objects.filter(pk=job_id).update(
        estado='terminado',
        terminado=timezone.now(),
        error='Algunos televisores fallaron.' if quedan_errores else '',
    )
    connections.close_all()
