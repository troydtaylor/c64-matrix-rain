; ===========================================================================
;  T H E   T U N E
; ---------------------------------------------------------------------------
;  An original piece: D natural minor, 125 BPM, 16 bars in two sections,
;  looping every 30.7 seconds.
;
;    voice 1   triangle bass
;    voice 2   pulse arpeggio, pulse width sweeping
;    voice 3   bars 1-8   the drum kit
;              bars 9-16  a lead melody with vibrato, with the kick and the
;                         snare still punching through it between phrases
;
;  Voice 3 was previously stuck on the noise waveform for ever, because the
;  rain read its oscillator at $D41B to choose glyphs.  The rain now builds
;  its own table of random numbers at boot, so this voice is free: it can
;  play pitched notes, which is what the whole B section is made of, and the
;  kick can be a real drum - a triangle wave swept from 481 Hz down to 60 Hz
;  over six frames - instead of a burst of noise.
;
;  The sequence is exactly 256 steps, so the position counter wraps on its
;  own and the loop needs no compare.
;
;  One step every 6 frames, driven from the same raster sync as the rain, so
;  the music cannot drift against the display.
; ===========================================================================

MTEMPO  = 6                     ; frames per step (6 = 125 BPM in 16ths)

W_BASS  = $10                   ; triangle
W_ARP   = $40                   ; pulse
W_LEAD  = $20                   ; sawtooth
W_NOISE = $80                   ; noise, for the hat and the snare
W_KICK  = $10                   ; triangle, swept down in pitch

; ---------------------------------------------------------------------------
musinit:
        lda #$00                ; wipe all 25 SID registers
        ldx #$18
.wipe   sta $d400,x
        dex
        bpl .wipe

        lda #$18                ; voice 1 bass: 8ms attack, 300ms decay,
        sta $d405               ; sustain 10, 300ms release
        lda #$a8
        sta $d406

        lda #$08                ; voice 2 arp: instant attack, 300ms decay,
        sta $d40c               ; no sustain - a pluck
        lda #$00
        sta $d40d

        lda #$00                ; arp pulse width starts narrow and sweeps
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
        jsr vibrato             ; lead wobble
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

        ; ---- voice 2: arpeggio --------------------------------------------
        lda seq2,y
        beq .s2
        cmp #$01
        bne .n2
        lda #W_ARP
        sta $d40b
        bne .s2
.n2     tax
        lda freqlo,x
        sta $d407
        lda freqhi,x
        sta $d408
        lda #W_ARP
        sta $d40b
        lda #W_ARP|$01
        sta $d40b
.s2

        ; ---- voice 3: drums in section A, lead in section B ---------------
        lda seq3,y
        bne .v3
        jmp .s3                 ; hold
.v3     cmp #$08
        bcc .notlead            ; $08 and up is a note; the voice 3 block is
        jmp .lead               ; too long for a short branch to reach it
.notlead
        cmp #$01
        bne .drum
        lda #$00                ; silence the voice
        sta $d412
        sta leadon
        sta dcnt
        jmp .s3

.drum   sta dtmp                ; 2 = hat, 3 = snare, 4 = kick
        lda #$00
        sta leadon
        sta dcnt
        lda dtmp
        cmp #$04
        beq .kick

        cmp #$02                ; hat and snare are both noise, and differ
        bne .snare              ; only in pitch and decay
        lda #$ff
        sta $d40e
        sta $d40f               ; top of the range: a short bright tick
        lda #$02                ; 48 ms decay
        bne .noisehit
.snare  lda #$00
        sta $d40e
        lda #$40
        sta $d40f               ; lower and grainier
        lda #$06                ; 204 ms decay
.noisehit
        sta $d413
        lda #$00
        sta $d414
        lda #W_NOISE
        sta $d412
        lda #W_NOISE|$01
        sta $d412
        jmp .s3

.kick   lda #$00                ; triangle, swept down by dtick each frame
        sta $d40e
        lda kickf+5
        sta $d40f
        lda #$07                ; 240 ms decay
        sta $d413
        lda #$00
        sta $d414
        lda #W_KICK
        sta $d412
        lda #W_KICK|$01
        sta $d412
        lda #$06
        sta dcnt                ; six frames of pitch sweep
        jmp .s3

.lead   tax                     ; a lead note: sawtooth, with vibrato
        lda #$00
        sta dcnt                ; cancel any kick sweep
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
        lda #$16                ; 8ms attack, 204ms decay, sustain 12
        sta $d413
        lda #$c6                ; 204 ms release
        sta $d414
        lda #W_LEAD
        sta $d412
        lda #W_LEAD|$01
        sta $d412
        lda #$01
        sta leadon
.s3

        inc mpos                ; 256 steps, so this wraps by itself

; ---- pulse width sweep on the arpeggio ------------------------------------
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
;  Kick drum: walk the frequency down one step per frame.
; ---------------------------------------------------------------------------
dtick:
        lda dcnt
        beq .nokick
        dec dcnt
        ldx dcnt
        lda #$00
        sta $d40e
        lda kickf,x
        sta $d40f
.nokick rts

; ---------------------------------------------------------------------------
;  Lead vibrato: one cycle every eight frames, about 6 Hz.
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
; kick sweep, read backwards: $20xx first (481 Hz), $04xx last (60 Hz)
kickf:  !byte $04,$06,$09,$0d,$13,$20
; vibrato, a triangle centred on 40
vibtab: !byte 40,60,80,60,40,20,0,20

; ---- state ----------------------------------------------------------------
mpos:   !byte 0
mtick:  !byte 1
pwlo:   !byte 0
pwhi:   !byte 6
pwdir:  !byte 0
dcnt:   !byte 0                 ; frames left in the kick sweep
dtmp:   !byte 0
leadon: !byte 0
leadlo: !byte 0
leadhi: !byte 0
vibph:  !byte 0

!source "musicdata.inc"
