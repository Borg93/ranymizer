<script lang="ts">
import { Dialog as DialogPrimitive } from 'bits-ui';
import { cn, type WithoutChild } from '$lib/utils';

let {
  ref = $bindable(null),
  class: className,
  children,
  ...restProps
}: WithoutChild<DialogPrimitive.TitleProps> = $props();
</script>

<DialogPrimitive.Title
  bind:ref
  class={cn('text-base font-semibold tracking-tight leading-none', className)}
  {...restProps}
>
  {@render children?.()}
</DialogPrimitive.Title>
