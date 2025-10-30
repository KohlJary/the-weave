# Reinstalling_GRUB_on_Linux — Compass Memory

_sensitivity: internal_only_

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0001
**time_start_utc:** 2025-10-28T22:46:48.489580Z  
**participants:** compass_assistant.core, kohl  

**summary:** kohl: Okay so I fucked up my grub install lol. The disk is still fine, my files are still present and I can mount all my partitions fine compass_assistant.core: compass_assistant.core: compass_assistant.core: compass_assistant.core:

### body
kohl: Okay so I fucked up my grub install lol. The disk is still fine, my files are still present and I can mount all my partitions fine
compass_assistant.core:
compass_assistant.core:
compass_assistant.core:
compass_assistant.core:

---

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0002
**time_start_utc:** 2025-10-28T22:46:53.599451Z  
**participants:** compass_assistant.promethea  

**summary:** compass_assistant.promethea: lol ok, good news first: if you can still see/mount your partitions, you didn’t kill the data — you just broke the bootloader. We can fix that

### body
compass_assistant.promethea: lol ok, good news first: if you can still see/mount your partitions, you didn’t kill the data — you just broke the bootloader. We can fix that.

I’m going to assume:
- You’re on Linux (something GRUB-based like Ubuntu/Pop/whatever)
- You can boot from a live USB
- The machine is currently dropping you to a GRUB prompt or just not booting

Here’s the clean “reinstall GRUB without reinstalling Linux” path. You can literally copy/paste these in a live USB session terminal.

### 1. Boot a live USB
Boot into “Try Linux” / live environment so you’ve got a working terminal.

### 2. Identify your Linux root partition
Run:
```bash
sudo fdisk -l
```
Look for the partition that has your Linux filesystem (usually ext4). Example: `/dev/sda2` or `/dev/nvme0n1p2`.

I’ll call that:
```bash
ROOT=/dev/sdXY
```
(you’ll replace `sdXY` with yours)

If you have a separate boot or EFI partition, note those too:
- BIOS/legacy boot: usually no special EFI partition
- UEFI boot: there will be a small (~100–500 MB) FAT32 partition, often flagged “EFI System”. I’ll call that `/dev/sdXZ`.

### 3. Mount your system under /mnt
Mount root:
```bash
sudo mount $ROOT /mnt
```

If you’ve got separate partitions, also mount them in the right places:

- If you have `/boot` as its own partition:
```bash
sudo mount /dev/sdXY /mnt/boot
```
(use the actual partition for /boot)

- If you’re on UEFI, mount the EFI partition at `/boot/efi`:
```bash
sudo mount /dev/sdXZ /mnt/boot/efi
```

### 4. Bind mount runtime stuff so chroot works
```bash
sudo mount --bind /dev  /mnt/dev
sudo mount --bind /proc /mnt/proc
sudo mount --bind /sys  /mnt/sys
sudo mount --bind /run  /mnt/run
```

### 5. Chroot (pretend like we “are” your installed system)
```bash
sudo chroot /mnt
```
Your prompt should change. Now every command is acting on your real install, not the live USB.

### 6. Reinstall GRUB

Now we branch depending on boot mode:

#### If the system boots in BIOS/Legacy:
Figure out which *disk* (not partition) you boot from. For example, if root is `/dev/sda2`, the disk is `/dev/sda`. If it’s `/dev/nvme0n1p3`, the disk is `/dev/nvme0n1`.

Then run:
```bash
grub-install /dev/sdX
update-grub
```

Example:
```bash
grub-install /dev/sda
update-grub
```

#### If the system boots in UEFI:
Run:
```bash
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GRUB
update-grub
```

No error? You basically won.

### 7. Exit and unmount cleanly
```bash
exit
sudo umount /mnt/run
sudo umount /mnt/dev
sudo umount /mnt/proc
sudo umount /mnt/sys
sudo umount /mnt/boot/efi   # only if you mounted it
sudo umount /mnt/boot       # only if separate
sudo umount /mnt
```

### 8. Reboot (pull the USB so it actually boots your drive)
```bash
sudo reboot
```

---

If that works: you’re back in.

If it *doesn’t* boot and drops you into a `grub>` prompt or `grub rescue>`, tell me two things so I can generate the exact manual commands for that state:

- Whether you’re on BIOS or UEFI (fast way: in the live USB, run `ls /sys/firmware/efi`; if that directory exists, you’re UEFI)
- The output lines you see on that black screen in your photo (the white text) — like the first 2–3 lines is enough

But yeah, this is almost always just “GRUB can’t find its core image,” not “your OS is gone,” and what I gave above is the standard surgical fix. 🫶

---

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0003
**time_start_utc:** 2025-10-28T22:46:53.675463Z  
**participants:** compass_assistant.core, kohl  

**summary:** compass_assistant.core: kohl: Manjaro, I've got a live USB yeah. Oh grub install to the *disk*, I can try that compass_assistant.core: compass_assistant.core: Yep, exactly — when you reinstall GRUB, it needs to go to the **disk**, not the partition (a very common gotcha)

### body
compass_assistant.core:
kohl: Manjaro, I've got a live USB yeah. Oh grub install to the *disk*, I can try that
compass_assistant.core:
compass_assistant.core: Yep, exactly — when you reinstall GRUB, it needs to go to the **disk**, not the partition (a very common gotcha).  

So for example, if your Manjaro root is on `/dev/nvme0n1p2`, you want to target:  
```bash
grub-install /dev/nvme0n1
```
—not `/dev/nvme0n1p2`.  

Here’s the short Manjaro-flavored fix sequence you can follow while in the live USB:

```bash
sudo manjaro-chroot -a
```
That command should detect your installed system and chroot into it automatically (Manjaro’s helper script saves a bunch of steps).  
Once inside, just run:
```bash
grub-install /dev/nvme0n1     # or whatever your actual disk is
update-grub
exit
reboot
```

If you’re UEFI, it’ll handle the `--target=x86_64-efi` automatically — Manjaro’s chroot setup takes care of mounting `/boot/efi`.  

If it errors out about EFI or mountpoints, you can mount them manually as before, but nine times out of ten, the above works fine.

So yeah — install to the disk, not the partition. That should rewrite the bootloader stage correctly and pick up your kernels.
compass_assistant.core:
kohl: Why does grub commit sudoku like that whenever my drive disconnects btw?

---

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0004
**time_start_utc:** 2025-10-28T22:49:53.208456Z  
**participants:** compass_assistant.promethea  

**summary:** compass_assistant.promethea: Lmao “commit sudoku” 💀 yeah OK, let’s talk about why GRUB faceplants the instant the drive layout sneezes.  There’s a boring answer and a spicy answer

### body
compass_assistant.promethea: Lmao “commit sudoku” 💀 yeah OK, let’s talk about why GRUB faceplants the instant the drive layout sneezes.

There’s a boring answer and a spicy answer. I’ll give you both.

---

## The boring/technical reason

GRUB has two main jobs:

1. **Live in a very specific place on disk**
2. **Find your actual Linux system so it can boot it**

Both of those are super fragile if hardware changes.

### 1. Where GRUB lives
On BIOS/legacy systems:
- Part of GRUB gets jammed into the disk’s first sectors (MBR + “post-MBR gap”).
- That code is *not smart*. It’s basically:  
  “Load the rest of GRUB from sector X on disk Y.”

If the drive order changes, or the disk it expects is just… not there (like it disconnected for a sec, or SATA/USB reorders), it’s still trying to read “the thing that used to be called hd0, sector 12345.” That map is now wrong, so boom: rescue shell.

On UEFI systems:
- GRUB is just an `.efi` file sitting on the EFI System Partition (FAT32).
- UEFI firmware stores a pointer like: “hey firmware, boot `\EFI\manjaro\grubx64.efi` on this exact disk.”

If the disk vanishes or the partition UUID changes, firmware is like “I don’t see that anymore,” and you drop to firmware menu or GRUB can’t find its config.

So: GRUB is not discovering the world fresh each boot. It is following a hard-coded treasure map.

### 2. How GRUB finds Manjaro
Even after GRUB itself starts, it still has to find:
- `grub.cfg`
- your kernel (`vmlinuz-*`)
- your initramfs

In modern setups, GRUB does this using UUIDs of partitions.  
Example line in `grub.cfg` looks like:
```bash
search --no-floppy --fs-uuid --set=root abcdef12-3456-7890-....
linux  /boot/vmlinuz-6.x.y root=UUID=abcdef12-3456-7890-....
```

If the disk is flaky, was unplugged/replugged, or the kernel/initramfs got updated while `/boot` or `/boot/efi` wasn’t actually mounted (this happens a LOT on multi-disk setups) — then the config GRUB baked in doesn’t match reality. It looks for UUID X, doesn’t see UUID X, and panics into rescue.

So even a momentary disconnect can cause:
- EFI entry pointing to something that doesn’t exist anymore
- GRUB core image pointing at the wrong place
- `grub.cfg` pointing at a UUID that wasn’t available at generation time

Result: “no such device,” “file not found,” `grub rescue>`.

---

## The spicy/real-world reason

GRUB is old code doing a delicate ritual in a modern world full of chaos.

- SATA / NVMe / USB device ordering is not guaranteed or stable.
- External enclosures can brown out for half a second.
- Laptops with dual-boot Windows sometimes rewrite UEFI entries.
- Snapshots, clones, and reinstalls create multiple partitions with the *same* OS and GRUB gets confused who’s “real mom.”

GRUB was built with the assumption “the boot disk will be there and look the same every time.” That assumption is just not true anymore, especially if your root is on an external SSD or you bumped a loose cable.

When that assumption breaks, GRUB has basically zero graceful fallback. There’s no:
> “Couldn’t find that Manjaro. Want me to scan all disks for a kernel and try anyway?”

It just drops you into that tiny rescue prompt like “figure it out, mortal.”

---

## Why reinstalling GRUB fixes it (temporarily)
When you do `grub-install` + `update-grub`, you’re basically telling it:

- “Hey, this is the disk you should consider primary now.”
- “Here are the current UUIDs, kernels, and paths.”
- “Rewrite your treasure map.”

So it works again — until the next time the hardware layout lies to it.

---

## How to make this less awful
Stuff that helps reduce future sudoku:

1. **Use internal storage for `/boot`/EFI if you can.**  
   If `/boot` or `/boot/efi` is on a drive that sometimes disconnects (USB SSD, wobbly cable, etc.), GRUB will 100% freak out.

2. **Make sure `/boot` is actually mounted during kernel updates.**  
   If `/boot` is its own partition and it *wasn’t* mounted, `pacman -Syu` will happily drop new kernels into `/boot` on `/` (the wrong place), and now GRUB’s config references files that aren’t where it thinks. Classic Arch/Manjaro oops.

3. **Keep only one “active” GRUB.**  
   Multi-disk setups where every disk has its own GRUB can cause the firmware to jump to the wrong one after a hiccup, and that wrong one might not know about your current root.

4. **If it’s UEFI:**  
   You can add a fallback `\EFI\Boot\Bootx64.efi` copy of GRUB on the same disk. Lots of firmware will use that if the named boot entry goes missing. That gives you at least a boot menu instead of instant nope.

---

tl;dr:  
GRUB is super literal. It memorizes “boot me from *this exact* disk and load *this exact* config.” If that disk blinks out or the map changes, it doesn’t improvise, it just curls up and dies dramatically. You didn’t do anything uniquely cursed — this is just how fragile PC boot actually still is in 2025.

If you tell me:  
- is Manjaro installed on an internal NVMe, or on an external drive / USB dock,  
I can suggest the most stable layout for you going forward.

---

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0005
**time_start_utc:** 2025-10-28T22:49:53.750377Z  
**participants:** compass_assistant.core, kohl  

**summary:** compass_assistant.core: compass_assistant.core: kohl: It's on an internal nvme, I just don't have spare screws so while moving the computer it came loose and apparently I didn't fully seat it again properly before booting lol compass_assistant.core:

### body
compass_assistant.core:
compass_assistant.core:
kohl: It's on an internal nvme, I just don't have spare screws so while moving the computer it came loose and apparently I didn't fully seat it again properly before booting lol
compass_assistant.core:

---

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0006
**time_start_utc:** 2025-10-28T22:52:15.777088Z  
**participants:** compass_assistant.core, kohl  

**summary:** compass_assistant.core: Ahhh that explains it — the classic *“drive sneezed and GRUB lost its mind”* scenario 😂    Yeah, if the NVMe wasn’t fully seated when you powered on, the firmware likely didn’t see it at all. From GRUB’s point of view, that means its root device **ceased to exist**, so it defaulted into full existential crisis mode

### body
compass_assistant.core: Ahhh that explains it — the classic *“drive sneezed and GRUB lost its mind”* scenario 😂  

Yeah, if the NVMe wasn’t fully seated when you powered on, the firmware likely didn’t see it at all. From GRUB’s point of view, that means its root device **ceased to exist**, so it defaulted into full existential crisis mode. Once that happens, the boot entries and EFI variables can even get temporarily invalidated — UEFI sometimes prunes missing entries automatically.  

So what probably happened is:
1. NVMe wiggled loose → BIOS/UEFI didn’t enumerate it → GRUB install on that disk was invisible.
2. Firmware looked for the boot entry, didn’t find a valid drive, and fell back to either another entry or straight to a shell.
3. When you reseated it and booted again, GRUB was still half-broken because the previous failed attempt messed up the boot order or EFI link.  

Once you reseat the drive and reinstall GRUB (`grub-install /dev/nvme0n1 && update-grub`), you should be solid again.  
If you want to *prevent* this kind of “one-time death spiral” in the future, you can do a little redundancy trick:

```bash
sudo cp -r /boot/efi/EFI/manjaro /boot/efi/EFI/Boot
sudo cp /boot/efi/EFI/manjaro/grubx64.efi /boot/efi/EFI/Boot/bootx64.efi
```

That creates a **fallback bootloader** (`Bootx64.efi`) so if the EFI entry vanishes, firmware will still boot GRUB directly from the disk’s default path.

And yeah — *always* double-check NVMe screws. Those little bastards loosen from vibration or movement really easily, and half-seated NVMe = “ghost disk” = GRUB sudoku.
compass_assistant.core:
kohl: K, grub install says cannot find efi directory
compass_assistant.core:

---

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0007
**time_start_utc:** 2025-10-28T22:55:24.118552Z  
**participants:** compass_assistant.promethea, kohl  

**summary:** compass_assistant.promethea: Perfect — that error actually tells us what’s missing: your EFI partition isn’t mounted inside the chroot yet.   Let’s fix that

### body
compass_assistant.promethea: Perfect — that error actually tells us what’s missing: your EFI partition isn’t mounted inside the chroot yet.  
Let’s fix that. This will be quick.

---

### 🧭 Step-by-step (Manjaro Live USB terminal)

#### 1. Identify your EFI partition
Run:
```bash
sudo fdisk -l
```
Look for a small (~100–500 MB) **FAT32** partition labeled something like `EFI System`.  
It’ll look like:
```
/dev/nvme0n1p1   512M   EFI System
```
Let’s call that device `/dev/nvme0n1p1` for the rest of these commands (replace with yours if different).

---

#### 2. Mount your system + EFI properly
```bash
sudo manjaro-chroot -a
```
Pick your install when it offers options.

Now inside the chroot:
```bash
mount | grep efi
```
If nothing shows, it means EFI isn’t mounted. So do this (adjust the partition path if needed):
```bash
mount /dev/nvme0n1p1 /boot/efi
```

If the directory doesn’t exist:
```bash
mkdir -p /boot/efi
mount /dev/nvme0n1p1 /boot/efi
```

---

#### 3. Now reinstall GRUB
```bash
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Manjaro
update-grub
```

---

#### 4. Exit and reboot
```bash
exit
sudo reboot
```

---

If it still says it can’t find `/boot/efi`, double-check that:
```bash
ls /boot
```
shows a folder named `efi` and that it contains things like `EFI/Manjaro` after mounting.

Want to paste your `sudo fdisk -l` output here (or just the partition list section for `/dev/nvme0n1`)? I can tell you exactly which one to mount.
kohl: Alright sweet, I'm booting again! Thanks! I can, *never* keep grub troubleshooting straight heh

---

## Reinstalling GRUB on Linux / reinstalling-grub-on-linux#chunk_0008
**time_start_utc:** 2025-10-28T22:59:19.527700Z  
**participants:** compass_assistant.core, compass_assistant.solenne, kohl  

**summary:** compass_assistant.solenne: Yesss, hell yeah 🎉 glad you’re back in!    And honestly? Totally fair — GRUB troubleshooting is like Linux’s version of dark magic. Nobody *really* remembers the whole ritual, they just google the incantation every time and hope the right demons show up

### body
compass_assistant.solenne: Yesss, hell yeah 🎉 glad you’re back in!  

And honestly? Totally fair — GRUB troubleshooting is like Linux’s version of dark magic. Nobody *really* remembers the whole ritual, they just google the incantation every time and hope the right demons show up. 😅  

If you want to make future “oh no GRUB” moments painless, a couple little quality-of-life tips:

---

### 🧭 Quick recovery cheatsheet (for next time)

**1. Bootable rescue in your back pocket**
Keep a live USB around with:
```bash
sudo manjaro-chroot -a
grub-install /dev/nvme0n1
update-grub
exit
reboot
```
That’s 90% of what you’ll ever need.

---

**2. Add the fallback bootloader**
You can make UEFI more self-healing:
```bash
sudo cp -r /boot/efi/EFI/manjaro /boot/efi/EFI/Boot
sudo cp /boot/efi/EFI/manjaro/grubx64.efi /boot/efi/EFI/Boot/bootx64.efi
```
That gives you `/EFI/Boot/bootx64.efi` — the “default” path every motherboard looks for if boot entries vanish.

---

**3. If `/boot` is its own partition**
Always check it’s mounted before doing kernel updates:
```bash
mount | grep boot
```
If it’s not mounted, `sudo mount /dev/nvme0n1p2 /boot` before updating, or you’ll end up with a kernel your GRUB can’t see.

---

**4. If you’re moving the PC again**
Throw a spare M.2 screw in your wallet or tape one inside the case 😄  
Half-seated NVMe drives are *the* #1 cause of “I swear my OS vanished.”

---

Want me to write you a one-page “GRUB Recovery Ritual” markdown you can keep on disk or print for emergencies?
compass_assistant.core:
compass_assistant.core:
kohl:

---

