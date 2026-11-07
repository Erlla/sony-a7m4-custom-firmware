# Maintainer handoff

## Publication scope

- Publish reusable implementation methods, authored source, input hashes and component verification boundaries. Do not publish specific experimental firmware versions, versioned delivery directories, package manifests or per-round test progress to GitHub. Keep those in the research repository.
- Preserve the root README structure: introduction and method index, without dated version announcements or a test-progress feed. The maintainer explicitly requested this separation.
- The custom-sound gallery uses the maintainer's corrected five-photo set: two menu locations, two settings screens and the audio picker. Shutter photos show the current generic title and Ciallo.wav; focus photos retain YEAH.WAV. Match shutter/focus captions to the visible menu title, update both language guides together and remove superseded gallery assets in a normal commit.
- Functional directories and commands are `native/feature-integration/` / `a7m4.feature_integration` and `native/jpeg-exif-dimensions/` / `a7m4.jpeg_exif_dimensions`. Exact input/output hashes remain mandatory; renaming a recipe does not make its fixed addresses portable.
- Do not rewrite repository history to remove older announcements. Make a normal scoped cleanup commit; generated firmware, manufacturer inputs and camera originals remain local.
- The desktop tool starts a fresh operation session on every normal launch, after requesting Windows elevation. Keep enrollment and historical evidence, but never use an old workflow, patch or USB-recovery pointer to gate the new session. Child processes inherit the new session; global process locks and live camera checks remain. `--verify` must stay noninteractive and local-only.
- Normal USB identity uses fresh standard descriptor reads after binding. PyUSB can cache an empty LANGID tuple after swallowing a USBError; preserve the underlying error, release failed handles and retry only descriptor reads for a bounded interval. Request only device-advertised languages and keep actual model/serial checks. A typed pre-authentication failure can restore the normal driver; an unknown binding or authenticated worker failure does not establish that boundary.

## Integration pitfalls

- See `native/feature-integration/REVIEW.md`. The isolated `aspect_pool_release` reuse counterexample omitted native mutex 9 around both allocation and release wrappers. With the outer mutex modeled, clearing finishes before reuse. Review every enclosing lock before reporting a concurrency defect.
- Per-thread replay needs separate stacks and actual blocking semantics at the modeled OS boundary; unconditional lock-success shims can create impossible schedules.
- Four old `.rela.dyn` aspect descriptor redirects are intentional; five legacy aspect entries branch to atomic selection. Inspect active paths rather than assuming every old entry executes old logic.
- Aspect text IDs AB60–AB63 collide with sound dialogs. Use AB4C–AB4F and modify only aspect-owned references.
- AP RX ranges for LUT and aspect do not overlap; shared metadata, relocation tails and constructors still need composition. Do not replace the main AP with an older standalone file.
- CP aspect code/BSS and its READY word must be independent of LUT. Preserve Thumb symbol typing for ARM calls.
- UXC offsets are u16 words: repack live records with the longest record last instead of appending indefinitely.
- Component tools require the source checkout and adjacent `native/`, pinned inputs and compiler, and LF source bytes. They do not produce a flashable package by themselves.
- Sound libmpr uses the active program-header table at 0x370000. Preserve sound extensions when adding the JPEG-specific EXIF source copy; do not use an old stock-library patch blindly.
- Offline native replay, encoded image structure and physical camera behavior are distinct evidence. Keep precise limits and avoid claims of complete color equivalence or performance from metadata alone.

## Custom LUT publication

- The SD JSON / 16-slot LUT method lives in methods/08-custom-lut. Publish functional descriptions and component identities, never internal firmware labels or per-round package manifests. Six screen photographs are maintainer-authorized.
- Preserve the AF helper relocation to 0xBA5718; old 0xBA4E00 belongs to LUT resident code in this integrated layout. Old standalone patch tools must keep their exact-input rejection.
- Retain the frozen basic feature-integration recipe, but do not describe its reference-slot limit as the current LUT feature. Preserve sound resources, aspect capture-copy chaining, MPR EXIF and AVCAM identities.
- Format/ABI versions, official input versions, software releases and BCD numeric examples are not internal firmware announcements. Do not alter measured numeric data when cleaning prose labels.

- User-facing feature introductions must describe current functions and operation only. Omit retired cache quotas, per-key cache explanations, iterative fixes, acceptance summaries and test-process conclusions in both languages and the root feature index. Keep implementation mechanics in technical references.

## README layout

- Both root READMEs strongly recommend having working Fastboot tools and the required cable/bridge ready before firmware updates, and seeking AI assistance when needed with documentation, errors and logs. Download links now point to Releases; do not restore the obsolete notice that complete firmware is not yet provided.
- Keep the opening flashing warning, then no-Fastboot installation, then a concise Fastboot method table and navigation, followed by declarations and acknowledgements. Keep detailed reports linked rather than reproducing test conclusions on the homepage.
- Credit Hearts-Ace/sony-a7r5-custom-firmware for native colour parameters, grid lifecycle research and R5ColorLab LUT fitting. The user explicitly excluded menu attribution; retain the custom LUT method entry.
- State the supported configuration prominently near the top in both languages: mainland-China-market Sony ILCE-7M4 (A7 IV / A7M4), officially sold in mainland China, running official Sony V6.02 before installation. Other regions and firmware versions have not been physically tested and are outside the release scope. The V6.02 requirement is the installation baseline, not the custom firmware's resulting version label.

- The custom LUT Off page has no Right-key RAM diagnostics entry. Keep the AP component identity in methods/08-custom-lut/reference-layout.json aligned with tools/disable_lut_ram_diagnostics.py and the subsequent custom-sound-policy chain; do not reintroduce the perf_active activation branch when rebuilding the GUI.

## Custom shutter sound policy and directory

- Mechanical, electronic front-curtain and electronic shutter modes share the shutter sound slot; changing capture mechanism preserves the user switch. Both sound slots import from PRIVATE/M4ROOT/GENERAL/SOUNDS. Keep feature prose, examples, resource profiles and title validation aligned in both languages.
- Fixed native source inputs preserve exported addresses. The runtime build-plan explicitly applies policy/directory changes after linking; installed.elf is authoritative. Use prepare_current_sound_sources.py for current C policy tests or a separately relinked port, not the unmodified reference C for current behaviour.
- The independent AP policy tool supports only listed complete SHA-256 identities. Do not change stock shutter getters to fake electronic mode. Scan/import prefix lengths, filename offsets and terminators must all change together.
- Update only the shutter photos when replacing those views; preserve focus and picker photos and the original supplied pixels. Menu and import confirmation text use indexed UXC records; update all horizontal/vertical banks without replacing LUT resources.
- Recipe JSON contains base64 patch bytes: do not describe release labels or copy delivery manifests into public docs. Keep numeric measurement data untouched during version-prose checks.

- The integrated CP uses native/custom-sounds/handoff and a7m4.custom_sound_handoff for mutual focus/shutter preemption. Keep APP admission, PIN admission and common begin gates together: APP can reject before common begin. Dispatch delayed APP requests through their original APP path. Stop opcode 2 is not pending Start 1; never clear native busy flags to force playback.
- Handoff state occupies 0x1564A84..0x1564F98, below Gamma fallback 0x1565000. Preserve BODY initialization, optional-page READY and CRC, the lens-AF helper at 0xBA5718 and the LUT/aspect code. The CP component chain in methods/08-custom-lut/reference-layout.json must match the handoff recipe. The frozen basic sound recipe uses a different CP layout and must retain its exact-input rejection.

## Shell / SSH methods

- Keep all terminal access recipes together in methods/09-shell-access, with one entry in both Fastboot method tables. Publish functional method names, component identities and activation details rather than internal candidate labels or the maintainer's current camera state.
- Telnet/USB share the ULOGIO restoration recipe; SSH uses the existing normal-system daemon plus startup/NSS/configuration; Multi UART uses the independent p1/Cetus/RP2040 bridge. SFTP and Wi-Fi do not add separate shell methods.
- Preserve the distinction between p1 and p15 libsencore offsets, the two-byte USB input/output payload, physical partition length and filesystem length, and persistent p10 paths. UART also changes p2 boot flags and cannot shoot in the updater environment.
- Reference inputs and upstream resources remain separately obtained. Do not publish personal SSH keys, camera backups, research paths, raw device logs or derivative firmware binaries. Do not describe this documentation set as a one-click installer or an integrated validation of SSH plus ULOGIO.

## Desktop tool maintenance

- The installation guides use five maintainer-supplied screenshots in workflow order: initial screen, unplug/update prompt, camera confirmation, operation ended, and USB recovery pending. The last two states are distinct; a pending-recovery screenshot does not show a restored connection. Keep both language guides and image numbering aligned.
- The published Release provides BODYDATA.DAT directly, without extraction; only the tool ZIP needs extraction. Its portable UI displays 1.00, while the source uses 1.0.0. The installed action records user confirmation without USB or installation readback; do not describe COMPLETE as an automatic firmware-installation check. Keep linked source/software guides' distribution status aligned with Releases.
- Task Scheduler may return an account name for a principal registered using a SID. Resolve both to SecurityIdentifier before comparison; retain action, arguments, directory, trigger and run-level checks. Record failed fields without adding account names or command-line data to diagnostics.
- First-use setup reuses matching installations and existing empty task folders, and creates only missing tasks. Do not delete running tasks or unknown operation records as retry cleanup. Fresh-state substitutes must model account-name readback, not just echo registration inputs.
- All six ordinary/service driver binding and coinstaller files belong to the separately supplied tools/driver asset group. Source builds must not depend on extra binaries in the checkout. Keep the exact per-file asset inventory and group fingerprint aligned.
- Software version is 1.0.0. Keep launcher, manifest, integrity gates, workflow and interface identifiers consistent. This source synchronization does not create a Release or publish binary assets; retain evidence locally and do not claim a Defender false-positive review result.

## AWB priority method

- The optional CP layer lives in methods/10-awb-priority and a7m4.awb_priority, with the exact profile a7m4/profiles/awb-priority.json. Default effective parameters are Ambience -1, Standard 0 and White 97; White 97 is a custom choice, not an FX2 factory value.
- The bilingual AWB guides compare this recipe with official FX2 1.01: Ambience -1, Standard 0 and White 88, with local coefficients 254/256/432. The factory table describes checked upgrade defaults and the Standard code branch; keep it distinct from the custom White 97 value and from final image colour.
- Apply this optional AWB layer after the current sound lifecycle CP output. Keep the older handoff identity supported as a frozen input, and preserve the preceding LUT/aspect/sound/AP/resource contracts. The LUT reference describes the component before optional AWB.
- Offsets 0x13293e/0x132948 are CP file offsets. Backup +0x930/+0x931 are record-relative and remain unchanged by this method. MOV.W preserves flags, and original SXTAB interprets 0xff as -1. Standard remains zero. Check complete input/output SHA-256, not camera labels.
- Publish the reusable source, bilingual method, component identities and verification limits. Keep package labels, full firmware, researcher paths, raw inputs and per-round delivery records local. Native/host replay and full-package offline checks do not establish physical installation or improved image quality.

## Persistent LUT and audio caches

- `native/persistent-cache` uses Zig 0.14.1 and a separate exact AP recipe. Preserve the original fixed modules and calls: the new RX wrapper occupies 0x9048000..0x9048DDF, extends the existing LOAD to 0x18DDF and adds no BSS. The AP chain continues from sound-policy output d61cf91f...1aea4 to 76cdb561...c5c6f1; CP, including its optional AWB layer, is untouched.
- LUT base caches follow internal content records, independently of the 16 user slots and CP bank references. Keep eight adjustments/strength separate. The frozen cache module retains its audio-result wrapper and ABI; the current lifecycle layer bypasses that wrapper. Preserve original JSON/WAV and fallback.
- Public feature prose describes reusable cached results without per-round speed/acceptance reports. Do not promise faster first selection of another LUT: AP compilation caching does not remove CP transfer, resource preparation or parameter application. Keep measured stage timings and future optimization work in the research repository.

## Sound lifecycle composition

- Keep the base handoff and persistent-cache recipes frozen and append `a7m4.custom_sound_lifecycle` for both AP and CP. Its current output restores the original sound WAV conversion entry while preserving LUT compilation caching. Do not describe persistent F0 audio results as active in the current sound method.
- CP admission publication and gain reads share the existing reader counter. Reservation checking and publication must remain in one reader section; use the original PIN cancellation for an idle focus reservation during preparation. Never clear busy or fake pending completion. Repeated focus restarts native DMA with the current waveform and gain.
- Preserve the resident reservation gate at 0xBA58C0, optional-page READY/CRC, the relocated lens-AF helper and Gamma space. AP policy/preparation helpers remain within the existing RX reservation. Publish module source and component identities, not device traces or package records.
- Keep startup guidance in both language guides: custom sounds may not take effect immediately after power-on; wait a few seconds. Do not promise an exact delay or complete resolution of all intermittent sound faults.
- The current LUT layout CP identity precedes the optional AWB layer. Extend AWB's exact component identity map for the new sound output, retaining older supported identities and the unchanged two instruction patches.

## Completed sound-request identifiers

- The AP lifecycle recipe includes token_reuse.c at 0x904B000 and the preserved private-parts entry stack instruction. Update the complete AP identity and shared LOAD metadata together. The CP recipe and optional AWB identities are unaffected by this AP-only change.
- Reuse is permitted only at the existing single-worker READY/attempted-zero boundary. Original ACK consumption, free and empty-queue checks define completion. Permanently skip all retired-query tokens, even after a late reply is consumed. Do not reset the endpoint, erase the ledger, change an in-flight identity or resend an uncertain mutation.
- If transport gains concurrent producers, retries or duplicate replies, review this completion contract before reusing identifiers. Keep change descriptions focused on the long-session failure and its handling; omit simulation totals, per-round progress and experimental firmware labels from public prose.

## Fastboot boot assets and focused Release archive

- The maintainer explicitly requested the two local historical boot assets, their source material and the entry/exit/backup/version/updater scripts. Only fastboot/assets/fastboot.bin and uart_boot.ino.uf2 are exceptions to the binary publication boundary; pin their identities in the checker and manifest. Never include prebuilt camera partitions, personal keys, backups, local paths or session state.
- The payload source is the historical ILCE-7M4-RE checkout. The UF2 matches the archived UART_TX build; publish its actual generated C++/PIO inputs with relative #line paths, not a later sketch presented as identical source. Keep upstream licensing status separate from project MIT.
- Entry and exit do not need a partition backup. Modification workflows retain the existing fresh-backup/plan/confirmation/full-readback sequence. Complete backup means payload-exposed eMMC, not separate CP NOR. Official restoration requires a same-camera original backup.
- tools/build_fastboot_release.py exports a focused source/script archive plus the two boot assets. Windows SDK tools, driver packages and SquashFS distributions remain separately supplied. Generated ZIPs stay local for the maintainer to upload; do not create a Release automatically or publish simulation totals or experimental camera firmware labels.
- The focused archive also includes the existing SD-recovery entry and read-only connection checker, their _launch_recovery.cmd, recover_sd/sd_recovery modules, exact sd-recovery.json and bilingual guide. Including only the BAT is insufficient. Keep the approved updater identities unchanged; recovery requires existing Fastboot and a suitable card-slot-1 BODYDATA.DAT. Exercise packaged launchers with a stub, never by running real recovery as a packaging check.

## Runtime-inclusive Fastboot portable archive

- The maintainer additionally requested Python, libraries, host tools and driver support in the ZIP. tools/build_fastboot_portable.py overlays the focused archive with supplied runtime assets and licenses; binaries and generated ZIPs stay out of Git. Keep the source-only builder usable separately.
- Embed Python under runtime/python and include the package root using ../../ with the trailing separator in the _pth file. Bare ../.. resolved to the runtime parent in the tested Windows embed build. Preserve isolation from PYTHONHOME, PYTHONPATH and a system interpreter. Both regular and recovery launchers must use the bundled interpreter; explicit A7M4_PYTHON overrides remain supported for development.
- Portable WinUSB uses signed, unmodified Zadig plus A7M4-Fastboot.cfg with VID 18D1, PID 4EE0 and Android's interface GUID F72FE0D4-CBCB-407D-8814-9ED673D0DD6B. Zadig does not automatically load a device preset from a command-line filename; ask the user to use Device > Load Preset Device and install WinUSB. Preserve the original INF path for separately registered legacy resource packs.
- Do not run the installer or recovery against a real device during packaging checks. Validate runtime imports, native tool operation, demo guards and dispatch with stubs. Bundle third-party license texts and matching SquashFS/compression/libwdi source archives; do not label the whole portable distribution MIT.

## Custom-ratio magnified playback

- Apply a7m4.aspect_playback after the current AP sound/lifecycle chain and the MPR JPEG EXIF component. Keep both exact input identities; do not replace the main AP or sound-enabled libmpr with old standalone libraries.
- Native STILL size recognition and JPEG aspect-valid classification are independent. Preserve the common matcher's 17 arguments and all existing callers; modify the JPEG-specific read getter only for known custom dimensions with invalid native layout.
- Layout value 0 is a native compatibility hint. Keep actual pixel dimensions, RAW geometry, known native ratios and unknown non-project inputs unchanged. JPEG/RAW+JPEG magnification was confirmed by the maintainer; do not expand that confirmation to HEIF or every display route.
- Public component metadata contains source/output hashes and stable entry locations. Keep private samples, complete firmware, research paths and iteration/package histories outside this repository.
