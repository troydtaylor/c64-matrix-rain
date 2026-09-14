; ===========================================================================
;  T H E   T U N E
; ---------------------------------------------------------------------------
;  An original piece written for this program.  Cinematic rather than
;  chiptune, which comes down to four things: a slow tempo (94 BPM), a
;  descending lament bass (D - C - Bb - A, with the A taken as a major
;  dominant for the bite of the C#), sustained slow-attack timbres instead of
;  plucky ones, and a half-time kick and snare instead of a busy kit.
;
;  Three voices carry five parts:
;
;    voice 1   the bass riff, sawtooth, six notes a bar, 3+3+2 across it
;    voice 2   the off-beat ostinato, plus the kick, which takes the two
;              steps of each bar where the ostinato rests anyway
;    voice 3   the upper line, slow attack with vibrato, plus the snare on
;              the backbeat.  The line re-swells after every snare, and that
;              pulsing-strings effect is the point, not a compromise.
;
;  The kick is a real drum: a triangle wave swept from 300 Hz down to 45 Hz
;  over eight frames, with a long decay so the low end of it booms.  It can be, because the rain no longer needs a SID voice
;  for its random numbers - see mkrnd in matrix.asm.
;
;  The sequence is exactly 256 steps, so the position counter wraps on its
;  own and the loop needs no compare.  One step every 8 frames, driven from
;  the same raster sync as the rain, so it cannot drift against the display.
; ===========================================================================

MTEMPO  = 8                     ; frames per step (8 = 94 BPM in 16ths)

W_BASS  = $20                   ; sawtooth - fat, and it cuts
W_OST   = $40                   ; pulse
W_UPPER = $20                   ; sawtooth
W_NOISE = $80                   ; noise, for the snare
W_KICK  = $10                   ; triangle, swept down in pitch
W_SUB   = $10                   ; triangle, the sub layer

; ---------------------------------------------------------------------------
musinit:
        lda #$00                ; wipe all 25 SID registers
        ldx #$18
.wipe   sta $d400,x
        dex
        bpl .wipe

        lda #$00                ; voice 1: instant attack, and sustain at full
        sta $d405               ; level, so each riff note holds its weight
        lda #$f9                ; right up to the next one.  750ms release.
        sta $d406

        lda #$00                ; the ostinato's pulse width sweeps
        sta pwlo
        lda #$06
        sta pwhi
        lda #$00
        sta pwdir

        sta mpos                ; A still zero
        sta dcnt
        sta leadon
        sta vibph
        lda #$01
        sta mtick               ; first step lands on the first frame

        lda #$0f
        sta $d418               ; volume
        rts

; ---------------------------------------------------------------------------
;  Called once per frame, straight after the rain update.
; ---------------------------------------------------------------------------
mplay:
        jsr dtick               ; kick drum pitch sweep
        jsr vibrato             ; upper line wobble
        dec mtick
        beq mstep
        jmp mpw                 ; between steps only the sweeps move

mstep:
        lda #MTEMPO
        sta mtick
        ldy mpos

        ; ---- voice 1: bass ------------------------------------------------
        lda seq1,y
        beq .s1                 ; hold
        cmp #$01
        bne .n1
        lda #W_BASS             ; note off
        sta $d404
        bne .s1                 ; always taken
.n1     tax
        lda freqlo,x
        sta $d400
        lda freqhi,x
        sta $d401
        lda #W_BASS             ; gate low then high, to retrigger
        sta $d404
        lda #W_BASS|$01
        sta $d404
.s1

        ; ---- voice 2: ostinato, and the kick ------------------------------
        lda seq2,y
        bne .v2any
        jmp .s2
.v2any  cmp #$08
        bcs .v2note
        cmp #$01
        bne .v2kick
        lda #W_OST              ; note off
        sta $d40b
        jmp .s2

.v2kick lda #$00                ; triangle, swept down by dtick each frame
        sta $d407
        lda kickf+7
        sta $d408
        lda #$09                ; 750 ms decay - it booms rather than taps
        sta $d40c
        lda #$00
        sta $d40d
        lda #W_KICK
        sta $d40b
        lda #W_KICK|$01
        sta $d40b
        lda #$08
        sta dcnt                ; eight frames of pitch sweep
        jmp .s2

.v2note and #$7f                ; bit 7 is a waveform flag, not pitch
        tax
        lda #$00
        sta dcnt                ; cancel any kick sweep
        lda freqlo,x
        sta $d407
        lda freqhi,x
        sta $d408
        lda seq2,y
        bmi .v2sub
        lda #$07                ; ostinato: pulse, short, a little sustain
        sta $d40c               ; so it drives rather than ticks
        lda #$30
        sta $d40d
        lda #W_OST
        sta $d40b
        lda #W_OST|$01
        sta $d40b
        jmp .s2
.v2sub  lda #$00                ; sub: triangle, instant attack, held at
        sta $d40c               ; full level - a near-pure fundamental
        lda #$f9                ; under the sawtooth riff
        sta $d40d
        lda #W_SUB
        sta $d40b
        lda #W_SUB|$01
        sta $d40b
.s2

        ; ---- voice 3: the upper line, and the snare -----------------------
        lda seq3,y
        bne .v3any
        jmp .s3
.v3any  cmp #$08
        bcs .v3note
        cmp #$01
        bne .v3snr
        lda #$00                ; silence the voice
        sta $d412
        sta leadon
        jmp .s3

.v3snr  lda #$00
        sta leadon
        sta $d40e
        lda #$40
        sta $d40f               ; mid-range noise: a body, not a tick
        lda #$07                ; 240 ms decay
        sta $d413
        lda #$00
        sta $d414
        lda #W_NOISE
        sta $d412
        lda #W_NOISE|$01
        sta $d412
        jmp .s3

.v3note tax                     ; sawtooth, slow attack, vibrato
        lda freqlo,x
        sta $d40e
        sta leadlo
        lda freqhi,x
        sta $d40f
        sta leadhi
        lda leadlo              ; park the vibrato centre 40 below the note,
        sec                     ; so the wobble is symmetrical about it
        sbc #40
        sta leadlo
        lda leadhi
        sbc #$00
        sta leadhi
        lda #$89                ; 100 ms attack - it swells in
        sta $d413
        lda #$9a                ; sustain 9, 1.5 s release - it sits behind
        sta $d414               ; the bass rather than on top of it
        lda #W_UPPER
        sta $d412
        lda #W_UPPER|$01
        sta $d412
        lda #$01
        sta leadon
.s3

        inc mpos                ; 256 steps, so this wraps by itself

; ---- pulse width sweep on the ostinato ------------------------------------
mpw:
        lda pwdir
        bmi .down
        lda pwlo
        clc
        adc #$18
        sta pwlo
        lda pwhi
        adc #$00
        sta pwhi
        cmp #$0c
        bcc .write
        lda #$ff
        sta pwdir
        bne .write
.down   lda pwlo
        sec
        sbc #$18
        sta pwlo
        lda pwhi
        sbc #$00
        sta pwhi
        cmp #$02
        bcs .write
        lda #$00
        sta pwdir
.write  lda pwlo
        sta $d409
        lda pwhi
        sta $d40a
        rts

; ---------------------------------------------------------------------------
;  Kick drum: walk voice 2's frequency down one step per frame.
; ---------------------------------------------------------------------------
dtick:
        lda dcnt
        beq .nokick
        dec dcnt
        ldx dcnt
        lda #$00
        sta $d407
        lda kickf,x
        sta $d408
.nokick rts

; ---------------------------------------------------------------------------
;  Upper line vibrato: one cycle every eight frames, about 6 Hz.
; ---------------------------------------------------------------------------
vibrato:
        lda leadon
        beq .novib
        inc vibph
        lda vibph
        and #$07
        tax
        lda leadlo
        clc
        adc vibtab,x
        sta $d40e
        lda leadhi
        adc #$00
        sta $d40f
.novib  rts

; ---------------------------------------------------------------------------
musoff:
        lda #$00
        sta $d418               ; volume off
        sta $d404               ; every gate released
        sta $d40b
        sta $d412
        rts

; ---- data -----------------------------------------------------------------
; kick sweep, read backwards: $14xx first (300 Hz), $03xx last (45 Hz)
kickf:  !byte $03,$03,$04,$05,$07,$09,$0c,$14
; vibrato, a triangle centred on 40
vibtab: !byte 40,60,80,60,40,20,0,20

; ---- state ----------------------------------------------------------------
mpos:   !byte 0
mtick:  !byte 1
pwlo:   !byte 0
pwhi:   !byte 6
pwdir:  !byte 0
dcnt:   !byte 0                 ; frames left in the kick sweep
leadon: !byte 0
leadlo: !byte 0
leadhi: !byte 0
vibph:  !byte 0

!source "musicdata.inc"
