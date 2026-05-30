<template>
  <!--
    The users table spans full width (utility: show as many columns as
    possible). The settings below it — the help prose and the flag-card
    sections — sit in a .adminReadingColumn so the same controls read at
    the same width as on the Settings tab. See frontend/DESIGN.md §1.
  -->
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="User"
        :inputs="AdminUserCreateUpdateInputs"
        max-width="20em"
      />
    </header>
    <AdminTable item-title="username" :headers="headers" :items="users">
      <template #no-data>
        <td class="adminNoData" colspan="100%">
          No Users.
          <div>
            This is an error. There should always be at least one Staff user.<br />
            You should not be able to see this page<br />
            You should restart Codex with the CODEX_RESET_ADMIN=1 variable
            set.<br />
            See the
            <a
              href="https://codex-comic-reader.readthedocs.io/#reset-the-admin-password"
              target="_blank"
            >
              documentation
            </a>
          </div>
        </td>
      </template>
      <template #[`item.isStaff`]="{ item }">
        <v-checkbox-btn :model-value="item.isStaff" disabled />
      </template>
      <!--
        Active is overloaded — Django's ``is_active`` flag controls
        both "can log in at all" and "has clicked the verification
        link" (when ``Verify New User Email`` is on). Split the
        display so inactive accounts that are *waiting* on a
        verification email are visually distinct from accounts an
        admin disabled manually.
      -->
      <template #[`item.isActive`]="{ item }">
        <v-chip
          :color="activeStatus(item).color"
          size="x-small"
          variant="tonal"
          :title="activeStatus(item).hint"
        >
          {{ activeStatus(item).label }}
        </v-chip>
      </template>
      <template #[`item.groups`]="{ item }">
        <RelationChips
          :pks="item.groups"
          :objs="groups"
          title-key="name"
          group-type
        />
      </template>
      <template #[`item.ageRatingMetron`]="{ item }">
        {{ ageRatingName(item.ageRatingMetron) }}
      </template>
      <template #[`item.lastActive`]="{ item }">
        <DateTimeColumn :dttm="item.lastActive" />
      </template>
      <template #[`item.lastLogin`]="{ item }">
        <DateTimeColumn :dttm="item.lastLogin" />
      </template>
      <template #[`item.dateJoined`]="{ item }">
        <DateTimeColumn :dttm="item.dateJoined" />
      </template>
      <template #[`item.actions`]="{ item }">
        <AdminCreateUpdateDialog
          table="User"
          :inputs="AdminUserCreateUpdateInputs"
          :old-row="item"
          max-width="20em"
          size="small"
          density="compact"
        />
        <ChangePasswordDialog
          :user="item"
          :is-admin-mode="true"
          size="small"
          density="compact"
        />
        <!--
          Resend the registration-verification email. Only shown when
          the user is still inactive AND the site requires email
          verification AND a working email backend is configured AND
          the row has an address on file. Hidden otherwise — silent
          UI rather than disabled buttons with tooltips, since each
          missing condition has its own remediation tab.
        -->
        <v-btn
          v-if="canSendVerification(item)"
          :icon="mdiEmailArrowRightOutline"
          variant="text"
          size="small"
          density="compact"
          title="Resend verification email"
          @click="sendVerification(item)"
        />
        <AdminDeleteRowDialog
          v-if="me.id !== item.pk"
          table="User"
          :pk="item.pk"
          :name="item.username"
          size="small"
          density="compact"
        />
      </template>
    </AdminTable>
    <div class="adminReadingColumn">
      <div class="adminProse ageRatingHelp">
        <h3>Age Rating Restrictions</h3>
        <p>
          Age-rating restrictions set a user's age rating ceiling. Comics that
          carry no age-rating tag are treated as if rated
          <strong>{{ ageRatingDefault }}</strong> &mdash; the current
          <em>Age Rating Default</em> set below.
        </p>
        <p>
          <strong>Admins are not exempt.</strong> An admin with an Age Rating
          ceiling set cannot see comics above that ceiling.
        </p>
      </div>
      <!--
        Account & Access controls live on the Users tab so admins can
        change registration / verification / anonymous-access policy
        next to the user list they affect. The Settings tab no longer
        mirrors these.
      -->
      <AdminSection title="Account & Access">
        <FlagCard
          v-for="key in ACCESS_FLAG_KEYS"
          :key="`f${key}`"
          :item-key="key"
        />
      </AdminSection>
      <AdminSection title="Age Ratings">
        <FlagCard
          v-for="key in AGE_RATING_FLAG_KEYS"
          :key="`f${key}`"
          :item-key="key"
        />
      </AdminSection>
    </div>
  </div>
</template>

<script>
import { mdiEmailArrowRightOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminUserCreateUpdateInputs from "@/components/admin/create-update-dialog/user-create-update-inputs.vue";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import FlagCard from "@/components/admin/tabs/flag-card.vue";
import RelationChips from "@/components/admin/tabs/relation-chips.vue";
import ChangePasswordDialog from "@/components/auth/change-password-dialog.vue";
import { UNRESTRICTED_LABEL, useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

const ACCESS_FLAG_KEYS = Object.freeze(["RG", "RV", "NU"]);
const AGE_RATING_FLAG_KEYS = Object.freeze(["AA", "AR"]);

export default {
  name: "AdminUsersTab",
  components: {
    AdminSection,
    AdminTable,
    AdminDeleteRowDialog,
    ChangePasswordDialog,
    AdminCreateUpdateDialog,
    DateTimeColumn,
    FlagCard,
    RelationChips,
  },
  data() {
    return {
      AdminUserCreateUpdateInputs: markRaw(AdminUserCreateUpdateInputs),
      ACCESS_FLAG_KEYS,
      AGE_RATING_FLAG_KEYS,
      mdiEmailArrowRightOutline,
      headers: [
        { title: "Username", key: "username", align: "start" },
        { title: "Email", key: "email", align: "start" },
        { title: "Staff", key: "isStaff" },
        { title: "Active", key: "isActive" },
        { title: "Groups", key: "groups" },
        { title: "Age Rating", key: "ageRatingMetron", align: "start" },
        { title: "Last Active", key: "lastActive" },
        { title: "Last Login", key: "lastLogin" },
        { title: "Joined", key: "dateJoined" },
        { title: "Actions", key: "actions", sortable: false },
      ],
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      users: (state) => state.users,
      groups: (state) => state.groups,
      ageRatingMetrons: (state) => state.ageRatingMetrons,
      flags: (state) => state.flags,
    }),
    ...mapState(useAuthStore, {
      me: (state) => state.user,
      adminFlags: (state) => state.adminFlags,
    }),
    ageRatingDefault() {
      return this._flagMetronName("AR", "Everyone");
    },
  },
  mounted() {
    /*
     * AgeRatingMetron populates the per-user dropdown and the column
     * name resolver; Flag drives the FlagCard sections. The admin
     * flags from the auth store gate the "Resend verification"
     * action button below.
     */
    this.loadTables(["Group", "User", "AgeRatingMetron", "Flag"]);
    this.loadAdminFlags();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables", "sendUserVerificationEmail"]),
    ...mapActions(useAuthStore, ["loadAdminFlags"]),
    canSendVerification(item) {
      return Boolean(
        !item.isActive &&
        item.email &&
        this.adminFlags.registerVerification &&
        this.adminFlags.emailEnabled,
      );
    },
    activeStatus(item) {
      if (item.isActive) {
        return {
          label: "Active",
          color: "success",
          hint: "User can log in.",
        };
      }
      if (this.adminFlags.registerVerification && item.email) {
        return {
          label: "Pending Verification",
          color: "warning",
          hint:
            "User has not clicked the email verification link yet." +
            " Use the email-arrow action to resend the link.",
        };
      }
      return {
        label: "Inactive",
        color: "error",
        hint: "User cannot log in.",
      };
    },
    sendVerification(item) {
      this.sendUserVerificationEmail(item.pk).catch(console.error);
    },
    ageRatingName(pk) {
      if (pk == undefined) {
        return UNRESTRICTED_LABEL;
      }
      const metron = (this.ageRatingMetrons || []).find((m) => m.pk === pk);
      return (metron && metron.name) || UNRESTRICTED_LABEL;
    },
    /** Resolve an admin-flag key to its metron's display name, or fallback. */
    _flagMetronName(key, fallback) {
      const flag = (this.flags || []).find((f) => f.key === key);
      if (!flag || flag.ageRatingMetron == undefined) {
        return fallback;
      }
      const metron = (this.ageRatingMetrons || []).find(
        (m) => m.pk === flag.ageRatingMetron,
      );
      return (metron && metron.name) || fallback;
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.ageRatingHelp {
  margin: 2em 0;
}
</style>
