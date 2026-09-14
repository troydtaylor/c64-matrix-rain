; ===========================================================================
;  T H E   T U N E
; ---------------------------------------------------------------------------
;  An original piece: D natural minor, 8 bars, 125 BPM, looping every 15.4s.
;
;    voice 1   triangle bass, root-root-fifth under each chord
;    voice 2   pulse arpeggio in straight 16ths, pulse width sweeping
;    voice 3   noise percussion - AND the rain's random number generator
;
;  That last one is the interesting constraint.  The rain reads $D41B, the
;  voice 3 oscillator, to pick its glyphs, so voice 3 must stay on the noise
;  waveform at frequency $FFFF for ever.  The drums are therefore played
;  entirely with the envelope: gate on, gate off, and a different decay rate
;  for the hat and the snare.  The oscillator never stops running, so the
;  random numbers are exactly as good as they were before the music existed.
;
;  One step every 6 frames, driven from the same raster sync as the rain, so
;  the timing is locked to the display and cannot drift.
; ===========================================================================

MTEMPO  = 6                     ; frames per step (6 = 125 BPM in 16ths)
SEQLEN  = 128                   ; steps in the loop

W_BASS  = $10                   ; triangle
W_ARP   = $40                   ; pulse
W_PERC  = $80                   ; noise

; ---------------------------------------------------------------------------
musinit:
        lda #$00                ; wipe all 25 SID registers
        ldx #$18
.wipe   sta $d400,x
        dex
        bpl .wipe

        lda #$ff                ; voice 3: noise, highest frequency, for ever
        sta $d40e
        sta $d40f
        lda #W_PERC
        sta $d412
        lda #$03                ; hat envelope to start with
        sta $d413

        lda #$18                ; voice 1 bass: 8ms attack, 300ms decay,
        sta $d405               ; sustain 10, 300ms release
        lda #$a8
        sta $d406

        lda #$08                ; voice 2 arp: instant attack, 300ms decay,
        sta $d40c               ; no sustain - a pluck
        lda #$00
        sta $d40d

        lda #$00                ; pulse width starts at 25% and sweeps
        sta pwlo
        lda #$06
        sta pwhi
        lda #$00
        sta pwdir               ; 0 = widening

        lda #$00
        sta mpos
        lda #$01
        sta mtick               ; first step happens on the first frame

        lda #$0f
        sta $d418               ; volume
        rts

; ---------------------------------------------------------------------------
;  Called once per frame, straight after the rain update.
; ---------------------------------------------------------------------------
mplay:
        dec mtick
        beq mstep
        jmp mpw                 ; between steps: only the pulse width moves

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
        lda #W_BASS             ; gate low, then high, to retrigger
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

        ; ---- voice 3: percussion, envelope only ---------------------------
        lda seq3,y
        beq .s3
        cmp #$01
        bne .n3
        lda #W_PERC
        sta $d412
        bne .s3
.n3     cmp #$02
        bne .snare
        lda #$03                ; hat:   72 ms decay
        bne .hit
.snare  lda #$06                ; snare: 204 ms decay
.hit    sta $d413
        lda #W_PERC             ; note the frequency is never touched
        sta $d412
        lda #W_PERC|$01
        sta $d412
.s3

        inc mpos
        lda mpos
        cmp #SEQLEN
        bne mpw
        lda #$00
        sta mpos

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
musoff:
        lda #$00
        sta $d418               ; volume off
        sta $d404               ; all gates released
        sta $d40b
        sta $d412
        rts

; ---- state ----------------------------------------------------------------
mpos:   !byte 0
mtick:  !byte 1
pwlo:   !byte 0
pwhi:   !byte 6
pwdir:  !byte 0

!source "musicdata.inc"
