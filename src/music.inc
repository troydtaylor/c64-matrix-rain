; ===========================================================================
;  T H E   T U N E
; ---------------------------------------------------------------------------
;  An original piece written for this program: big beat.  Fast breakbeat
;  drums, a funk bass with octave pops, short stabs that sound sampled, and
;  a breakdown that drops the kit and builds it back.  125 BPM, 16 bars,
;  looping every 30.7 seconds.
;
;    voice 1   the bass: square wave, E minor pentatonic, with explicit
;              note-offs in the data so it is rhythmic rather than a drone
;    voice 2   the stabs: narrow pulse, quick decay.  A stab flagged with
;              bit 7 is a SID chord - the player arpeggiates a minor triad
;              through it at one note per frame, which is how a single voice
;              on this chip has always faked a chord.  The breakdown holds
;              long notes on the same voice.
;    voice 3   the kit: kick (triangle, pitch-swept 240 Hz down to 48 Hz in
;              four frames), snare and hat (noise), one hit per step
;
;  The sequence is exactly 256 steps, so the position counter wraps on its
;  own and the loop needs no compare.  One step every 6 frames, driven from
;  the same raster sync as the rain, so it cannot drift against the display.
; ===========================================================================

MTEMPO  = 6                     ; frames per step (6 = 125 BPM in 16ths)

W_BASS  = $40                   ; pulse, 50% - a square: fat, hollow
W_STAB  = $40                   ; pulse, narrow and sweeping: nasal, brassy
W_NOISE = $80                   ; noise, for the snare and the hat
W_KICK  = $10                   ; triangle, swept down in pitch

; ---------------------------------------------------------------------------
musinit:
        lda #$00                ; wipe all 25 SID registers
        ldx #$18
.wipe   sta $d400,x
        dex
        bpl .wipe

        lda #$00                ; voice 1 bass: 50% pulse width
        sta $d402
        lda #$08
        sta $d403
        lda #$06                ; instant attack, 204ms decay,
        sta $d405               ; sustain 8, instant release
        lda #$80
        sta $d406

        lda #$05                ; voice 2 stabs: instant attack, 168ms decay,
        sta $d40c               ; sustain 8 (so held notes hold), 48ms release
        lda #$82
        sta $d40d

        lda #$00                ; stab pulse width starts narrow and sweeps
        sta pwlo
        lda #$02
        sta pwhi
        lda #$00
        sta pwdir

        sta mpos                ; A still zero
        sta dcnt
        sta arpon
        sta arpph
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
        jsr arp                 ; chord arpeggio on the stabs
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

        ; ---- voice 2: stabs, plain or arpeggiated -------------------------
        lda seq2,y
        bne .v2any
        jmp .s2
.v2any  cmp #$08
        bcs .v2note
        lda #W_STAB             ; note off
        sta $d40b
        lda #$00
        sta arpon
        jmp .s2
.v2note sta v2tmp
        and #$7f                ; bit 7 is the chord flag, not pitch
        tax
        stx arpbase
        lda freqlo,x
        sta $d407
        lda freqhi,x
        sta $d408
        lda #W_STAB
        sta $d40b
        lda #W_STAB|$01
        sta $d40b
        lda #$00
        sta arpph
        lda v2tmp
        and #$80
        sta arpon               ; $80 = arpeggiate, $00 = plain
.s2

        ; ---- voice 3: the kit ---------------------------------------------
        lda seq3,y
        bne .v3any
        jmp .s3
.v3any  cmp #$01
        bne .v3drum
        lda #$00                ; silence
        sta $d412
        jmp .s3
.v3drum cmp #$04
        beq .v3kick
        cmp #$02
        bne .v3snr
        lda #$ff                ; hat: noise at the top of the range,
        sta $d40e               ; 48 ms decay - a closed tick
        sta $d40f
        lda #$02
        sta $d413
        jmp .v3hit
.v3snr  lda #$00                ; snare: mid-range noise, 204 ms decay
        sta $d40e
        lda #$60
        sta $d40f
        lda #$06
        sta $d413
.v3hit  lda #$00
        sta $d414
        sta dcnt                ; cancel any kick sweep
        lda #W_NOISE
        sta $d412
        lda #W_NOISE|$01
        sta $d412
        jmp .s3
.v3kick lda #$00                ; kick: triangle, swept down by dtick
        sta $d40e
        lda kickf+3
        sta $d40f
        lda #$06                ; 204 ms decay
        sta $d413
        lda #$00
        sta $d414
        lda #W_KICK
        sta $d412
        lda #W_KICK|$01
        sta $d412
        lda #$04
        sta dcnt                ; four frames of pitch sweep
.s3

        inc mpos                ; 256 steps, so this wraps by itself

; ---- pulse width sweep on the stabs ---------------------------------------
mpw:
        lda pwdir
        bmi .down
        lda pwlo
        clc
        adc #$20
        sta pwlo
        lda pwhi
        adc #$00
        sta pwhi
        cmp #$05
        bcc .write
        lda #$ff
        sta pwdir
        bne .write
.down   lda pwlo
        sec
        sbc #$20
        sta pwlo
        lda pwhi
        sbc #$00
        sta pwhi
        cmp #$01
        bcs .write
        lda #$00
        sta pwdir
.write  lda pwlo
        sta $d409
        lda pwhi
        sta $d40a
        rts

; ---------------------------------------------------------------------------
;  Kick drum: walk voice 3's frequency down one step per frame.
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
;  SID chord: cycle a minor triad through the stab, one note per frame.
; ---------------------------------------------------------------------------
arp:
        lda arpon
        beq .noarp
        inc arpph
        lda arpph
        cmp #$03
        bcc .arpok
        lda #$00
        sta arpph
.arpok  tax
        lda arpbase
        clc
        adc arpoff,x
        tax
        lda freqlo,x
        sta $d407
        lda freqhi,x
        sta $d408
.noarp  rts

; ---------------------------------------------------------------------------
musoff:
        lda #$00
        sta $d418               ; volume off
        sta $d404               ; every gate released
        sta $d40b
        sta $d412
        rts

; ---- data -----------------------------------------------------------------
; kick sweep, read backwards: $0Fxx first (240 Hz), $03xx last (48 Hz)
kickf:  !byte $03,$05,$08,$0f
; minor triad, in semitones above the root
arpoff: !byte 0,3,7

; ---- state ----------------------------------------------------------------
mpos:   !byte 0
mtick:  !byte 1
pwlo:   !byte 0
pwhi:   !byte 2
pwdir:  !byte 0
dcnt:   !byte 0                 ; frames left in the kick sweep
v2tmp:  !byte 0
arpon:  !byte 0
arpbase: !byte 0
arpph:  !byte 0

!source "musicdata.inc"
